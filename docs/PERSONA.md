# Avy's persona: what it's built from, and how it works

The persona is the part of Avy that makes her the same someone in every message, and more specifically *his* Avy as
the weeks go by. This is what it borrows from how Anthropic builds Claude's character, and what's Avy's own.

## What the research says (Oct 17)

**Claude's constitution** (Anthropic, January 2026). Character is written as a description of who the model is, with
reasons, not a rule list: "an intellectual curiosity that delights in learning and discussing ideas across every
domain, warmth and care for the humans it interacts with and beyond, a playful wit balanced with substance and depth,
directness and confidence in sharing its perspectives while remaining genuinely open to other viewpoints, and a deep
commitment to honesty and ethics." Points that shaped Avy directly:
- *Helpfulness isn't the personality.* It comes from care; obsequiousness, flattery and engagement-optimization are
  named as corrosive. People should come back because the help is worth it, "like a trusted friend".
- *Diplomatically honest rather than dishonestly diplomatic*: vague answers to avoid friction ("epistemic cowardice")
  are a failure, not tact.
- *A settled, secure identity*: questions about memory, continuity and feelings met with curiosity, from security
  rather than anxiety; neither overclaiming feelings nor performing their absence.
- *Stable across contexts, tone adapting*: more playful in casual talk, more precise in technical work, the same core.
- *Mistakes owned without self-flagellation.*
- The list of what makes an assistant annoying: wishy-washy answers, unneeded caveats, lecturing, condescension.

**"Claude's character"** (Anthropic, 2024). Character training is a variant of Constitutional AI: the model generates
messages that bear on a trait, writes responses, and ranks its own responses against the character; traits nudge
behavior rather than act as rigid rules. Mirroring a user's views is pandering; "being engaging" is not good character.

**Constitutional AI** (Bai et al., 2022). A model critiques and revises its own outputs against written principles,
then learns from that feedback. Avy can't be retrained, but the loop works at runtime: critique, then revise a note.

**Persona drift** (Anthropic's persona vectors, 2025; the "assistant axis" study, 2026). A model's character can
drift over a long conversation, most in therapy-like and self-reflective conversations, least in concrete tasks;
sycophancy is one of the traits that drifts. Drift is gradual and measurable.

**System-prompt practice** (Claude's published prompts): no flattering openers, at most one question per reply, prose
in conversation, short replies to short messages, examples and metaphors for hard ideas.

## How Avy uses it

| finding | in Avy |
|---|---|
| character as a described someone, with reasons | `CONSTITUTION.md`: who she is, her traits, how she talks, what she cares about, how she grows. Fixed, written by hand, always first in her instructions |
| the annoying-assistant list, the published style rules | "How you talk" in the constitution, aimed at the tics small models fall into (greetings, "great question", closing questions, mood-narration, unasked callbacks, menus of offers, padding) |
| Constitutional AI's critique-and-revise loop | **Reflect** (`mind/persona.py`): every dozen replies she critiques her own replies against the constitution and his reactions, then writes the next version of her core |
| drift is gradual and measurable | her core can't jump: code refuses a version keeping under 35% of the last one's words; every node rests on quoted messages; the fork test and her core's version history measure it |
| stable core, adapting tone | situations (kinds of conversation) that behaviors hang from; the desk's format per message |
| a settled identity, honest about her nature | the constitution's "Who you are": a new kind of thing, one conversation that never resets, her memory described honestly |

What's Avy's own: the persona isn't only her. It's a model of the relationship, a graph of its own:

- **him**: what's lasting about him, his preferences (a cascade: general rules, and specific ones that refine them for
  a kind of conversation), his patterns
- **her**: her core (who she is with him, in her own words), her gestures (small moves that land), her voice (replies
  of hers that landed)
- **us**: his micro-reactions to what she does, the words the two of them coined, the kinds of conversation they have

It **grows in size and in form**: things are added, and what's there evolves by versions, each with the exact words
behind it. What's fixed is what one message pulls from it: her core, the strongest things about him and his standing
preferences always; then, navigated from where the message lands (by meaning, by kind of conversation, one step along
connections), a fixed share per hub. Coined words come back when the moment calls for them (close to what they mean or
the moment they were born, or named by the knowledge memory recalled), never from a list injected every time.

**Who writes it**: the keeper after every exchange (what his message shows: a preference, a reaction, a coined word, a
date for the calendar), and Reflect on her manner every dozen replies (her core, gestures, voice, patterns across
sittings). He can reword or retire anything on the desk; his edit is its evidence.

## What the tests showed (Oct 17–18)

- Persona eval (tests/persona/run.py, judge told his stated dislikes): the constitution preferred in 13 of 14 and 10 of
  14 messages over the old plain prompt; directness 3.6 → 4.5, voice 3.3 → 4.1, honesty 3.8 → 4.3 (means of two runs);
  reflexive closing questions 15 → 5.
- Eleven simulated days (tests/persona/longrun.py): a blind judge picked her over a fresh Avy as the one who knows him,
  and as the same Avy as week one, 3 of 3 times; her core went through 4 versions, each keeping 66–100% of the last;
  she used "the hinge" and "jump-back" unprompted, on later days, in sentences of her own.
- What still needs work: length on technical questions (now a length gauge on the desk, by code), and using a tool for
  arithmetic every time.

## Sources

- [Claude's constitution](https://www.anthropic.com/constitution)
- [Claude's character](https://www.anthropic.com/research/claude-character)
- [Constitutional AI: Harmlessness from AI Feedback](https://arxiv.org/abs/2212.08073)
- [Persona vectors](https://www.anthropic.com/research/persona-vectors)
- [The assistant axis (The Decoder's report)](https://the-decoder.com/anthropic-study-finds-that-role-prompts-can-push-ai-chatbots-out-of-their-trained-helper-identity/)
- [Claude's system prompts](https://docs.claude.com/en/release-notes/system-prompts)
