# Recipes

Practical use cases for LIMA. Each recipe describes what you get, when to use it, and how to customize the prompt for your needs.

> **These are starting points, not templates.** The goal is to inspire experimentation. Open the workflow, look at the prompt, and make it yours.

---

## Meeting Recap

**What you get:** Structured summary with participants, decisions, and action items.

**When to use:** After any meeting where you need to share outcomes or track commitments.

**Prompt tweaks to try:**

Add to the extraction prompt:
```
Also extract:
- Participants mentioned (names or roles)
- Decisions made (what was agreed)
- Open questions (unresolved items)
- Next meeting topics (if mentioned)
```

**Tips:**
- Mention names clearly when recording: "Sarah agreed to..." helps the AI attribute actions
- State decisions explicitly: "We decided to..." makes extraction more reliable
- End with a recap: "To summarize, the action items are..." gives the AI a clear signal

---

## Customer Call Follow-Up

**What you get:** Call summary focused on customer needs, commitments made, and follow-up tasks.

**When to use:** After sales calls, support calls, or customer interviews.

**Prompt tweaks to try:**

Add to the extraction prompt:
```
Also extract:
- Customer pain points (problems they mentioned)
- Feature requests (what they asked for)
- Commitments we made (what we promised)
- Competitor mentions (other products discussed)
- Sentiment (positive, neutral, negative)
```

**Tips:**
- Note the customer's name at the start of recording
- Explicitly state any promises: "I'll send you the proposal by Friday"
- Capture verbatim quotes when they express strong opinions

---

## Action Items Extractor

**What you get:** A focused checklist of tasks with owners and due dates.

**When to use:** When you primarily want a task list, not a full summary.

**Prompt tweaks to try:**

Simplify the prompt to focus only on actions:
```
Extract ONLY action items from this transcript.

For each action item, provide:
- Task: What needs to be done
- Owner: Who is responsible (if mentioned)
- Due date: When it's due (if mentioned)
- Context: One sentence of background

Output as a markdown checklist:
- [ ] **Task** - Owner - Due date
  - Context
```

**Tips:**
- Use clear language: "I need to..." or "Can you..." signals a task
- Mention deadlines explicitly: "by end of week" or "before the launch"
- Assign ownership: "John will handle the design review"

---

## Brainstorm Capture

**What you get:** Organized collection of ideas with categories and potential next steps.

**When to use:** After creative sessions, planning discussions, or solo idea dumps.

**Prompt tweaks to try:**

Add to the extraction prompt:
```
Also extract:
- Ideas mentioned (brief description of each)
- Categories (group related ideas)
- Favorites (ideas that got positive reactions)
- Concerns (potential problems mentioned)
- Suggested next steps (how to move forward)
```

**Tips:**
- Don't filter yourself - capture all ideas, even wild ones
- Note reactions: "I love that idea" or "that might be tricky"
- End with prioritization: "The top three ideas are..."

---

## Daily Standup Log

**What you get:** Quick personal log of what you did, what's next, and blockers.

**When to use:** End of day reflection or async standup updates.

**Prompt tweaks to try:**

```
Format this as a daily standup update:

## What I accomplished today
- (bullet points)

## What I'm working on next
- (bullet points)

## Blockers or concerns
- (bullet points, or "None" if clear)

Keep it concise - one line per item.
```

**Tips:**
- Record at the end of your day when work is fresh
- Mention specific deliverables: "finished the API integration"
- Be honest about blockers - they're useful for your future self

---

## Interview Notes

**What you get:** Structured notes from job interviews or user research sessions.

**When to use:** After conducting interviews where you need to compare candidates or synthesize feedback.

**Prompt tweaks to try:**

```
Extract from this interview:

## Candidate/Participant
- Name (if mentioned)
- Role/Background

## Key Strengths
- (evidence-based observations)

## Concerns or Gaps
- (areas that need follow-up)

## Notable Quotes
- (verbatim quotes that stood out)

## Overall Impression
- (one paragraph summary)

## Follow-up Questions
- (things to clarify in next round)
```

---

## Making Your Own Recipe

The best recipe is one tailored to your specific needs. Here's how to experiment:

### 1. Start with the Default

Process a recording with the standard prompt. Look at what's extracted.

### 2. Identify Gaps

What's missing? What would make this more useful for your workflow?

### 3. Add Specific Sections

Edit the prompt to extract additional fields. Be explicit about format.

### 4. Test and Iterate

Process a few recordings. Adjust the prompt based on results.

### 5. Consider Context

Some tweaks work better with certain recording styles. A brainstorm needs different handling than a formal meeting.

---

## Try This

> **Customize for your domain:** If you work in sales, add "budget discussed" and "timeline mentioned". If you're in product, add "user story" and "acceptance criteria".

> **Change the output format:** Instead of markdown, try asking for JSON output that you can process further.

> **Combine recipes:** Create a "Customer Meeting" recipe that merges Meeting Recap with Customer Call Follow-Up.

---

## Next Steps

- [Customizing Your AI](customizing-your-ai.md) - Where to find and edit the prompt
- [BACKLOG](../BACKLOG.md) - More ideas for extending LIMA
