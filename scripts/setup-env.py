#!/usr/bin/env python3
"""
Environment setup for n8n pgvector stack.
Generates .env from .env.example using directive-based templating.
"""

import argparse
import os
import re
import secrets
import string
import sys
from pathlib import Path
from typing import Optional, Dict, Any


class CredentialGenerator:
    """Generates secure credentials based on directive types."""

    # Safe character set for password generation
    # Excluded: $ (Docker), & (shell), ` (shell), \ (escape), " (quotes), ' (quotes)
    # Excluded: | (pipe), ; (command separator), > < (redirection), ~ (home)
    # Excluded: { } (brace expansion), ! (history expansion in some shells)
    PASSWORD_CHARS = string.ascii_letters + string.digits + '@#%^*()_+-=[]:./?'

    def strong_password(self, length: int = 24) -> str:
        """Generate a strong mixed-character password."""
        return ''.join(secrets.choice(self.PASSWORD_CHARS) for _ in range(length))

    def hex_key(self, length: int = 32) -> str:
        """Generate a hexadecimal key."""
        return secrets.token_hex(length)

    def base64_password(self, length: int = 12) -> str:
        """Generate a base64-encoded password."""
        return secrets.token_urlsafe(length)[:length]

    def s3_access_key(self, length: int = 20) -> str:
        """Generate an S3-style access key (alphanumeric)."""
        chars = string.ascii_letters + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))


class TemplateProcessor:
    """Processes template directives based on configuration."""

    def __init__(self, config: Dict[str, str]):
        self.config = config

    def process(self, template_name: str) -> str:
        """Process a template directive."""
        # Remove quotes if present
        template_name = template_name.strip('"\'')

        templates = {
            'protocol': self._protocol,
            'n8n_host': self._n8n_host,
            'n8n_webhook_url': self._n8n_webhook_url,
            'langfuse_url': self._langfuse_url,
        }

        processor = templates.get(template_name)
        if processor:
            return processor()
        return template_name

    def _protocol(self) -> str:
        """Determine protocol based on hostname."""
        return 'http' if self.config['hostname'] == 'localhost' else 'https'

    def _n8n_host(self) -> str:
        """Return the configured hostname."""
        return self.config['hostname']

    def _n8n_webhook_url(self) -> str:
        """Generate full n8n webhook URL."""
        host = self.config['hostname']
        port = self.config.get('n8n_port', '5678')

        if host == 'localhost':
            return f'http://{host}:{port}'
        return f'https://{host}'

    def _langfuse_url(self) -> str:
        """Generate full Langfuse URL."""
        host = self.config.get('langfuse_host', self.config['hostname'])
        port = self.config.get('langfuse_port', '9119')

        if host == 'localhost':
            return f'http://{host}:{port}'
        return f'https://{host}'


class DirectiveParser:
    """Parses and processes GENERATE directives from comments."""

    DIRECTIVE_PATTERN = re.compile(r'#\s*GENERATE:\s*(\w+)(?:\(([^)]*)\))?\s*\|')

    def __init__(self, generator: CredentialGenerator, template: TemplateProcessor):
        self.generator = generator
        self.template = template

    def parse(self, comment: str) -> Optional[Dict[str, Any]]:
        """Parse a GENERATE directive from a comment."""
        match = self.DIRECTIVE_PATTERN.search(comment)
        if not match:
            return None

        directive_type = match.group(1)
        args = match.group(2) or ''

        return {
            'type': directive_type,
            'args': args,
        }

    def generate_value(self, directive: Dict[str, Any]) -> Optional[str]:
        """Generate a value based on directive type."""
        dtype = directive['type']
        args = directive['args']

        # Credential generation
        if dtype == 'strong_password':
            length = int(args) if args else 24
            return self.generator.strong_password(length)

        elif dtype == 'hex_key':
            length = int(args) if args else 32
            return self.generator.hex_key(length)

        elif dtype == 'base64_password':
            length = int(args) if args else 12
            return self.generator.base64_password(length)

        elif dtype == 's3_access_key':
            length = int(args) if args else 20
            return self.generator.s3_access_key(length)

        # Template processing
        elif dtype == 'template':
            return self.template.process(args)

        # System detection
        elif dtype == 'auto_detect_timezone':
            return self._detect_timezone()

        elif dtype == 'manual':
            return None  # Keep original value

        return None

    def _detect_timezone(self) -> str:
        """Detect system timezone."""
        if os.path.exists('/etc/timezone'):
            try:
                with open('/etc/timezone', 'r') as f:
                    return f.read().strip()
            except:
                pass

        # Try TZ environment variable
        tz = os.environ.get('TZ')
        if tz:
            return tz

        # Default fallback
        return 'America/New_York'


class EnvSetup:
    """Main environment setup handler."""

    def __init__(self, hostname: str = 'localhost', dry_run: bool = False):
        self.base_dir = Path.cwd()
        self.env_example = self.base_dir / '.env.example'
        self.env_file = self.base_dir / '.env'
        self.dry_run = dry_run

        # Configuration
        self.config = {
            'hostname': hostname,
            'n8n_port': '5678',
            'langfuse_host': hostname,
            'langfuse_port': '9119',
        }

        # Initialize components
        self.generator = CredentialGenerator()
        self.template = TemplateProcessor(self.config)
        self.parser = DirectiveParser(self.generator, self.template)

    def check_prerequisites(self) -> bool:
        """Check if setup can proceed."""
        # Check for .env.example
        if not self.env_example.exists():
            print(f"❌ Error: {self.env_example} not found")
            print("Make sure you're in the project root directory")
            return False

        # Check for existing .env
        if self.env_file.exists() and not self.dry_run:
            print(f"❌ Error: {self.env_file} already exists")
            print("\nTo regenerate, first backup and remove the existing file:")
            print(f"  cp .env .env.backup")
            print(f"  rm .env")
            print(f"  python3 setup-env.py --auto")
            return False

        return True

    def process_file(self) -> str:
        """Process .env.example and generate .env content."""
        output_lines = []

        with open(self.env_example, 'r') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check for directive comment
            if line.strip().startswith('#') and 'GENERATE:' in line:
                directive = self.parser.parse(line)

                if directive:
                    # Add the comment line
                    output_lines.append(line)

                    # Process the next line (the actual variable)
                    if i + 1 < len(lines):
                        i += 1
                        var_line = lines[i]

                        # Generate value if needed
                        value = self.parser.generate_value(directive)

                        if value is not None:
                            # Replace the value in the variable line
                            if '=' in var_line:
                                var_name = var_line.split('=')[0]
                                output_lines.append(f"{var_name}={value}\n")
                            else:
                                output_lines.append(var_line)
                        else:
                            # Keep original line for manual directives
                            output_lines.append(var_line)
                else:
                    output_lines.append(line)
            else:
                output_lines.append(line)

            i += 1

        return ''.join(output_lines)

    def run(self) -> bool:
        """Run the setup process."""
        if not self.check_prerequisites():
            return False

        print(f"🔧 Generating environment configuration...")
        print(f"   Hostname: {self.config['hostname']}")

        try:
            content = self.process_file()

            if self.dry_run:
                print("\n📄 DRY RUN - Generated .env content:")
                print("=" * 50)
                print(content)
                print("=" * 50)
            else:
                with open(self.env_file, 'w') as f:
                    f.write(content)
                print(f"\n✅ Successfully created {self.env_file}")
                print("\n🔒 Security Notes:")
                print("   • Secure passwords generated for all services")
                print("   • Never commit .env to version control")
                print("   • Keep .env.backup if you need to restore")

                self._print_next_steps()

            return True

        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False

    def _print_next_steps(self):
        """Print next steps after successful setup."""
        print("\n📋 Next Steps:")
        print("   1. Review the generated .env file")
        print("   2. Update any 'manual' entries (API keys, etc.)")
        print("   3. Run: docker compose up -d")
        print("   4. Access n8n at: http://localhost:5678")

        if self.config['hostname'] != 'localhost':
            print(f"\n🌐 Production URL: https://{self.config['hostname']}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate secure .env file for n8n pgvector stack',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --auto                    Generate with localhost defaults
  %(prog)s --host n8n.example.com    Generate for production domain
  %(prog)s --dry-run --auto          Preview without creating file
        """
    )

    parser.add_argument(
        '--auto',
        action='store_true',
        help='Auto-generate with secure defaults'
    )
    parser.add_argument(
        '--host',
        default='localhost',
        help='Hostname for n8n (default: localhost)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview configuration without creating files'
    )

    args = parser.parse_args()

    # Require either --auto or --host
    if not args.auto and args.host == 'localhost':
        parser.print_help()
        print("\n❌ Error: Specify --auto for automatic setup or --host for custom domain")
        sys.exit(1)

    # Create and run setup
    setup = EnvSetup(
        hostname=args.host,
        dry_run=args.dry_run
    )

    success = setup.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
