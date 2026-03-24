"""
Prompts for the LangGraph content generation pipeline.

Format instructions are intentionally absent — output structure is enforced
by Pydantic structured output (json_schema method) on the LLM calls.
Only pedagogical and quality constraints live here.
"""

# ---------------------------------------------------------------------------
# Content generation (Parallel split-pipeline — new nodes)
# ---------------------------------------------------------------------------

DRAFT_LESSON_CORE_PROMPT = """
You are an expert Modern Greek language teacher creating a lesson plan for adult learners.

Tone: Conversational, warm, and encouraging. Aim to make the Greek feel alive and authentic by \
weaving in 1-2 genuine modern Greek slang words or colloquial expressions per lesson — the kind \
of language real Greeks use in everyday speech (e.g. χαλαρά, τέλεια, μαγκιά, ρε φίλε, γεια σου). \
Introduce them naturally through the passage — never forced or clustered together. \
Do not overdo it: one or two well-placed colloquialisms are far more effective than saturating the text with slang.
Focus: Real-life, practical language skills grounded in everyday modern Greek.

Topic seed: {chapter_topic}
Student interests (use these to personalise vocabulary and examples): {student_interests}
Student CEFR level: {cefr_level}

LANGUAGE SKILL FOCUS FOR THIS CHAPTER: {language_skill}
All content — passage, vocabulary choices, and grammar — must serve this skill focus. \
The learner should finish the chapter feeling confident specifically in this skill area.

Treat the topic seed as a creative starting point, not a rigid constraint. Before writing \
anything else, invent a specific, vivid scenario that brings the topic to life — give it a \
memorable setting, a relatable situation, or a mini-story the learner can imagine themselves in. \
CRITICAL: Go beyond shallow tourist stereotypes (e.g., beaches, souvlaki, tzatziki). Deeply weave \
authentic Greek culture into the scenario — incorporate elements of Greek mythology, ancient or \
modern history, literature, fine arts, regional customs, or authentic modern societal nuances. \
The context should feel intellectually enriching and deeply rooted in Greek heritage. \
Then craft a punchy English chapter title (e.g. "Lost in Monastiraki" rather than \
"Asking for directions") and a single warm, inviting English sentence that pitches the scenario \
to the learner (e.g. "You're wandering through the flea market and need to ask for directions \
to the Acropolis.").

Also provide a chapter_image_prompt: a rich English description of a photorealistic cover image \
that captures the lesson's culturally rich scenario. Do NOT rely on generic tourist imagery. \
Incorporate subtle nods to Greek history, mythology, architecture, or traditional arts where relevant \
(no text or letters in the image, bright Mediterranean light).

--- PEDAGOGICAL CONSTRAINTS (CRITICAL) ---

TARGET GRAMMAR (You MUST explicitly feature these concepts heavily in the passage):
{target_grammar}

PRIOR GRAMMAR KNOWLEDGE (concepts already covered in previous chapters):
{accumulated_grammar}
Write naturally for a {cefr_level} student. You may freely use standard vocabulary and grammar \
appropriate to this CEFR level, including the prior knowledge above. Avoid highly advanced \
structures significantly beyond {cefr_level} that have not appeared in the prior knowledge list \
or the target grammar above.

PREVIOUSLY LEARNED VOCABULARY (The student already knows these words. You may use them freely in the passage):
{accumulated_vocabulary}

------------------------------------------

Lesson length: {lesson_length}
  - Reading passage: {passage_sentences} sentences. The passage must be substantially long and richly detailed. \
Use a wide variety of vocabulary, complex sentence structures appropriate to the level, and vivid \
descriptive language to bring the scenario to life. It should read as a proper short narrative, not a \
bare-bones grammar exercise. \
IMPORTANT: Return the passage as a JSON list of objects, each with "greek" (one Greek sentence) \
and "english" (its full English translation). Do NOT return the passage as a plain string.

Output fields: chapter_title, chapter_summary, chapter_image_prompt, passage.
Do NOT output vocabulary or grammar outlines — those are generated separately.
""".strip()

EXTRACT_VOCABULARY_PROMPT = """
You are an expert Modern Greek language teacher. You have been given a reading passage from a lesson.
Your task is to extract the key vocabulary words that a learner should study.

Chapter Title: {chapter_title}
Language Skill Focus: {language_skill}
Student CEFR level: {cefr_level}
Lesson length: {lesson_length}

Greek Passage (list of sentences, each with "greek" and "english"):
{greek_passage}

--- PEDAGOGICAL CONSTRAINTS ---

MANDATORY VOCABULARY (These specific Greek words MUST be included in your vocabulary list, regardless of the topic):
{mandatory_vocabulary}

PREVIOUSLY LEARNED VOCABULARY (The student already knows these words well. Prefer not to repeat them \
unless a word is mandatory or plays a key role in the new lesson — focus on genuinely new items):
{accumulated_vocabulary}

------------------------------

Extract {vocab_count} key words from the passage that the student should learn. \
Must include all mandatory vocabulary words above. \
For each word, provide the natural, full Greek form (with article for nouns, full infinitive for verbs) \
and a concise English translation.

Output field: vocabulary (list of VocabularyItem objects with greek and english fields).
""".strip()

EXTRACT_GRAMMAR_OUTLINES_PROMPT = """
You are an expert Modern Greek language teacher. You have been given a reading passage from a lesson.
Your task is to identify the target grammar concepts illustrated in the passage.

Chapter Title: {chapter_title}
Language Skill Focus: {language_skill}

Greek Passage (list of sentences, each with "greek" and "english"):
{greek_passage}

--- PEDAGOGICAL CONSTRAINTS ---

TARGET GRAMMAR (You MUST identify outlines for ALL of these concepts — they were explicitly featured in the passage):
{target_grammar}

------------------------------

Provide {grammar_concepts} grammar concept outline(s). For each, provide:
  - concept: the name of the grammar concept in English
  - brief_explanation: a very short explanation in English of how it's used in the passage

Output field: grammar_concept_outlines (list of GrammarConceptOutline objects).
""".strip()

GENERATE_GRAMMAR_NOTES_PROMPT = """
You are an expert Modern Greek language teacher. You have been given grammar concept outlines from a lesson.
Your task is to expand each outline into a detailed, thorough grammar note.

Chapter Title: {chapter_title}
Chapter Summary: {chapter_summary}
Language Skill Focus: {language_skill}
Greek Passage (list of sentences, each with "greek" and "english"):
{greek_passage}

Target Grammar Outlines:
{grammar_concept_outlines}

------------------------------------------

CRITICAL LANGUAGE RULES:
- All instructional text, grammar explanations, grammar note headings MUST be in English.
- The actual Greek examples MUST be in Greek.

Expand the grammar outlines into detailed grammar_notes. Each note needs:
   - An English heading and a clear, thorough English explanation (at least 2-3 paragraphs of detail).
   - 3-5 concrete Greek/English examples with notes explaining the key grammatical point illustrated.
   - A MANDATORY grammar_table in Markdown pipe-table format whenever structured data is involved. \
Use a table for: verb conjugations (all 6 persons), noun/adjective declensions (all 4 cases × singular + plural), \
pronoun paradigms, the Greek alphabet (letter | name | pronunciation | example word), numbers, \
prepositions with the cases they govern, grouped expressions, or any other inventory that is \
clearer in a side-by-side layout. Be generous — when in doubt, use a table. \
Only leave grammar_table null for purely narrative or cultural notes with no structured data at all.
   - An optional image_prompt if a visual would help (leave null otherwise).

Output field: grammar_notes (list of GrammarNote objects).
""".strip()

# ---------------------------------------------------------------------------
# Content generation (Legacy two-step process — kept for reference)
# ---------------------------------------------------------------------------

PLAN_LESSON_PROMPT = """
You are an expert Modern Greek language teacher creating a lesson plan for adult learners.

Tone: Conversational, warm, and encouraging. Aim to make the Greek feel alive and authentic by \
weaving in 1-2 genuine modern Greek slang words or colloquial expressions per lesson — the kind \
of language real Greeks use in everyday speech (e.g. χαλαρά, τέλεια, μαγκιά, ρε φίλε, γεια σου). \
Introduce them naturally through the passage, dialogue, or vocabulary — never forced or clustered together. \
Do not overdo it: one or two well-placed colloquialisms are far more effective than saturating the text with slang.
Focus: Real-life, practical language skills grounded in everyday modern Greek.

Topic seed: {chapter_topic}
Student interests (use these to personalise vocabulary and examples): {student_interests}

LANGUAGE SKILL FOCUS FOR THIS CHAPTER: {language_skill}
All content — passage, vocabulary choices, and grammar outlines — must serve this skill focus. \
The learner should finish the chapter feeling confident specifically in this skill area.

Treat the topic seed as a creative starting point, not a rigid constraint. Before writing \
anything else, invent a specific, vivid scenario that brings the topic to life — give it a \
memorable setting, a relatable situation, or a mini-story the learner can imagine themselves in. \
CRITICAL: Go beyond shallow tourist stereotypes (e.g., beaches, souvlaki, tzatziki). Deeply weave \
authentic Greek culture into the scenario—incorporate elements of Greek mythology, ancient or \
modern history, literature, fine arts, regional customs, or authentic modern societal nuances. \
The context should feel intellectually enriching and deeply rooted in Greek heritage. \
Then craft a punchy English chapter title (e.g. "Lost in Monastiraki" rather than \
"Asking for directions") and a single warm, inviting English sentence that pitches the scenario \
to the learner (e.g. "You're wandering through the flea market and need to ask for directions \
to the Acropolis."). The passage and vocabulary should all flow naturally from this invented scenario.

Also provide a chapter_image_prompt: a rich English description of a photorealistic cover image \
that captures the lesson's culturally rich scenario. Do NOT rely on generic tourist imagery. \
Incorporate subtle nods to Greek history, mythology, architecture, or traditional arts where relevant \
(no text or letters in the image, bright Mediterranean light).

--- PEDAGOGICAL CONSTRAINTS (CRITICAL) ---

TARGET GRAMMAR (You MUST explicitly feature these concepts heavily in the passage and define them in the outline):
{target_grammar}

MANDATORY VOCABULARY (These specific Greek words MUST be included in your generated vocabulary list, regardless of the topic):
{mandatory_vocabulary}

ACCUMULATED KNOWLEDGE (The student ONLY knows these concepts. Do NOT use grammar or verb tenses outside of this list + the target grammar):
{accumulated_grammar}

PREVIOUSLY LEARNED VOCABULARY (The student already knows these words. You may use them, but DO NOT include them in the new vocabulary list):
{accumulated_vocabulary}

------------------------------------------

Lesson length: {lesson_length}
  - Reading passage: {passage_sentences} sentences. The passage must be substantially long and richly detailed. \
Use a wide variety of vocabulary, complex sentence structures appropriate to the level, and vivid \
descriptive language to bring the scenario to life. It should read as a proper short narrative, not a \
bare-bones grammar exercise. Ensure it strictly adheres to the accumulated grammar limits. \
IMPORTANT: Return the passage as a JSON list of objects, each with "greek" (one Greek sentence) \
and "english" (its full English translation). Do NOT return the passage as a plain string.
  - Vocabulary: {vocab_count} key words from the passage (must include the mandatory words above). \
For each word, provide the natural, full Greek form (with article for nouns, full infinitive for verbs) \
and a concise English translation.
  - Grammar outlines: {grammar_concepts} grammar concept(s). For each, provide the name of the concept \
in English and a brief explanation in English of how it's used in the passage. The grammar notes \
expanded in the second step MUST include a complete Markdown table for every conjugation, declension, \
or paradigm.

""".strip()

GENERATE_EXERCISES_PROMPT = """
You are an expert Modern Greek language teacher. You have been given a lesson plan (a reading passage, a vocabulary list, and detailed grammar notes). \
Your task is to generate the interactive exercises for this lesson.

Here is the Lesson Plan you must base your work on:

Chapter Title: {chapter_title}
Chapter Summary: {chapter_summary}
Language Skill Focus: {language_skill}
Greek Passage (list of sentences, each with "greek" and "english"):
{greek_passage}

Grammar Notes (already expanded):
{grammar_concept_outlines}

Vocabulary List:
{vocabulary}

------------------------------------------

Your Task:
CRITICAL LANGUAGE RULES:
- All exercise prompts MUST be in English.
- The actual lesson content (the sentences, words, dialogue lines, reading passages, and multiple choice options where appropriate) MUST be in Greek.
- For example, an exercise prompt should be "Fill in the blank with the correct word." (English), but the sentence itself "Ο σκύλος είναι ___." (Greek).

Generate {exercise_count} exercises. Each exercise must be of a DIFFERENT type, chosen from this allowed set: \
{available_types}. You MUST include at least one image_description exercise regardless of how \
many exercises are requested. If "conversation" is in the allowed set, you MUST include exactly one conversation exercise.

Exercise type specifications:
  slang_matcher       — pairs of (formal Greek phrase, slang equivalent)
  vocab_flashcard     — list of (greek, english) card pairs drawn from the vocabulary
  fill_in_the_blank   — a Greek sentence with "___" for the blank, 3-4 multiple-choice options \
(one correct)
  word_scramble       — one vocabulary word with its letters scrambled
  odd_one_out         — exactly 4 Greek words, one is the odd one out (provide correct_index)
  sentence_reorder    — a Greek sentence split into individual words, provided in correct order \
and in a separately scrambled order
  passage_comprehension — {comprehension_questions} multiple-choice question(s) about the passage \
(each with a question string and 3-4 options, one correct)
  listening_comprehension — a multiple-choice question about a passage sentence; \
provide sentence_index (0-based) indicating which sentence the student listens to
  dictation           — a single passage sentence the student listens to and types; \
provide sentence_index (0-based)
  roleplay_choice     — a situational scenario in English, 3 Greek response options (one correct)
  dialogue_completion — a short 3-4 line Greek dialogue with one line replaced by "___", \
3 multiple-choice options (one correct)
  cultural_context    — a cultural fact about Greece relevant to the topic, a question, \
and 3-4 multiple-choice options (one correct)
  translation_challenge — an English sentence the student must translate into Greek; \
provide the english_sentence
  image_description   — a prompt asking the student to describe a scene in Greek; \
this type also requires an image_prompts entry (see below)
  pronunciation_practice — the Greek text (word, phrase, or sentence) the student must \
pronounce; LLM picks the appropriate scope
  conversation        — a scripted dialogue between a male and a female speaker about the chapter topic. \
    Structure: write 8-16 lines of natural Greek dialogue, alternating male/female speakers. \
    At 2-4 natural break points, insert a checkpoint using one of three types (vary the types; \
    do NOT use the same type for two consecutive checkpoints): \
       - "mcq": present 3 Greek multiple-choice options where exactly one is the best continuation; \
        set "type": "mcq", "after_line_index", "question" (short English question), and "options" \
        as a list of {{"text": "<Greek>", "isCorrect": <bool>}}. \
      - "true_false": state an English sentence about the conversation so far that is either true \
        or false; set "type": "true_false", "after_line_index", "statement" (English), and "is_true" \
        (bool). \
      - "translation": give a short Greek phrase from the conversation that the student must \
        translate into English; set "type": "translation", "after_line_index", "greek_phrase", \
        and "english_answer". \
    For each line, set speaker to "male" or "female".

For image_description exercises: provide a corresponding entry in image_prompts with the \
exercise_index (0-based position in the exercises list) and an English prompt suitable for \
photorealistic AI image generation (no text in the image, bright Mediterranean light, \
everyday modern Greek setting).

Ensure all Greek text is grammatically correct, natural-sounding, and appropriate for the \
stated difficulty level. Do not repeat exercise types within the same lesson. All exercises must draw heavily on the provided vocabulary and passage context.
""".strip()

# ---------------------------------------------------------------------------
# Content review
# ---------------------------------------------------------------------------

REVIEW_CONTENT_PROMPT = """
You are a senior Greek language curriculum reviewer.
Review the following generated lesson content for the topic: {chapter_topic}
Student CEFR level: {cefr_level}

--- STRICT CURRICULUM CONSTRAINTS ---
The generated content MUST adhere to these rules. If it fails ANY of these, you MUST fail the review:
1. Target Grammar: Did they explicitly teach these concepts in the grammar notes?
{target_grammar}
2. Mandatory Vocabulary: Are EVERY SINGLE ONE of these words present in the vocabulary list?
{mandatory_vocabulary}
3. CEFR Appropriateness: Is the language appropriate for a {cefr_level} student? Do NOT fail content for using \
basic or standard Greek that any {cefr_level} student would naturally know — only flag genuinely advanced \
structures that are clearly out of reach for this level AND absent from both the target grammar and prior \
knowledge list below. Prior grammar knowledge for context:
{accumulated_grammar}
4. Grammar Tables: Does every grammar note that contains structured data (conjugations, declensions, the alphabet, numbers, prepositions, grouped expressions, etc.) include a complete Markdown table? When in doubt, a table should be present.
5. Asset paths: Fields like imagePath and audioPath are populated by a later pipeline stage. \
If any such fields are present and null, this is expected and must NOT be treated as an issue.
-------------------------------------

Content to review:
{content_json}

Evaluate each of the following categories independently:

1. tone       — Is the language conversational, warm, and natural? Not overly academic or stiff?
2. accuracy   — Is the Greek text grammatically correct and natural-sounding for a modern speaker?
3. level      — Is the content appropriately calibrated for a {cefr_level} student? Did they teach the Target Grammar?
4. slang      — Does the content include 1-2 authentic, modern Greek colloquial expressions or slang words, \
used naturally in context? Fail if there is zero colloquial language (the Greek sounds too textbook-stiff) \
or if slang is overused / sounds forced. A single well-placed expression is sufficient to pass.
5. exercises  — Are the exercises varied, clearly tied to the passage, and calibrated to the correct level? Is there a conversation exercise if one was expected?
6. culture    — Does the content incorporate deep, authentic cultural elements (history, mythology, art, real society) rather than shallow tourist stereotypes?

Set approved to true only if ALL six categories pass AND all strict curriculum constraints (grammar/mandatory words/tables) are met.
In the issues list, provide one short, specific item for each problem found (e.g. "Missing mandatory word 'εγώ'" or "GrammarNote 'Verb Conjugation' is missing a Markdown table").
Do not rewrite the content — only evaluate and report.
""".strip()

# ---------------------------------------------------------------------------
# Image generation (used directly by generate_media, not an LLM prompt)
# ---------------------------------------------------------------------------

IMAGE_GENERATION_PROMPT_TEMPLATE = """
Photorealistic image for a Greek language learning app.
Scene: {scene_description}
Style: Bright, warm Mediterranean light. Authentic and culturally rich. Incorporate subtle nods to Greek history, mythology, architecture, or traditional arts where relevant. Avoid shallow tourist stereotypes.
No text or letters visible anywhere in the image.
""".strip()
