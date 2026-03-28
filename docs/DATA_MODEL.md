# Firestore Data Model & Schema

This document outlines the NoSQL structure for our language learning app. Strict adherence to this schema is required across all components.

## 1. Top-Level Collections

### `users`
Documents representing the students.

**Document ID:** `{firebase_uid}`

```json
{
  "email": "user@example.com",
  "displayName": "Alex Student",
  "status": "pending", // Enum: ["pending", "active"]. Controls access to the app.
  "createdAt": "Timestamp",
  "lastActive": "Timestamp",
  "progress": {
    "currentPhaseId": "phase_1_the_tourist",
    "completedChapterIds": ["chapter_1_airport", "chapter_2_taverna"],
    "lastProgressSummary": "You've mastered the accusative case and can now confidently order food at a taverna.", // Plain-text Gemini-generated summary of the last completed chapter.
    "xp": 450 // Basic gamification
  },
  "vocabularyList": [
    // Simple list of words the user has encountered and should know
    { "wordId": "word_kalimera", "learnedAt": "Timestamp" }
  ]
}
```

### `phases`
The high-level groupings of content (e.g., Phase 1: The Tourist). Think of these as books.

**Document ID:** `{phaseId}` (e.g., `phase_1`)

```json
{
  "title": "The Tourist",
  "description": "Survival basics for your first trip to Greece.",
  "order": 1,
  "isActive": true
}
```

### `chapters`
The individual units within a phase (e.g., Chapter 1: At the Airport).

**Document ID:** `{variantId}` (e.g., `p1_c1_airport`)

```json
{
  "phaseId": "phase_1",
  "curriculumChapterId": "p1_c1",
  "topic": "At the Airport",
  "title": "Lost in Monastiraki",
  "order": 1,
  "languageSkill": "Speaking", // Optional label e.g. "Speaking", "Reading", "Listening", "Writing", "Grammar".
  "length": "medium", // Optional: "short", "medium", or "long"
  "introduction": "A 2-3 paragraph English introduction designed to spark interest before the lesson begins.",
  "summary": "You're wandering through the flea market and need to ask for directions.",
  "passage_text": "Ο Γιώργος είναι στο Μοναστηράκι...",
  "passageAudioUrl": "gs://public-assets-bucket/chapters/p1_c1_airport/passage_p1_c1_airport.mp3",
  "sentenceAudioUrls": [
    "gs://public-assets-bucket/chapters/p1_c1_airport/sentence_00_p1_c1_airport.mp3"
  ],
  "coverImageUrl": "gs://public-assets-bucket/images/chapter_cover.jpg",
  "grammarNotes": [
    {
      "heading": "The Accusative Case",
      "explanation": "Used for direct objects and after certain prepositions.",
      "examples": [
        {
          "greek": "Βλέπω τον άνδρα.",
          "english": "I see the man.",
          "note": null,
          "audioUrl": "gs://public-assets-bucket/chapters/p1_c1_airport/grammar_00_ex_00.mp3" // Per-example audio. Present on newly generated chapters; absent on legacy chapters.
        }
      ],
      "grammar_table": "| Person | Singular | Plural |\n|--------|----------|--------|\n| 1st | τον | τους |", // Optional Markdown pipe-table for conjugation/declension paradigms.
      "imageUrl": "gs://public-assets-bucket/images/grammar_note_00.jpg",
      "audioUrl": null // Legacy: single combined audio for all examples. Present only on chapters generated before per-example audio was introduced. New chapters use per-example audioUrl on each example instead.
    }
  ],
  "grammarSummary": "## Lost in Monastiraki\n\n### Grammar: The Accusative Case\n...", // Pre-generated Markdown reference (grammar tables + key vocabulary + tips). Generated once by the content-cli pipeline and shared across all students. Displayed in the Grammar Book page only after the student completes the chapter.
  "vocabulary": [
    {
      "greek": "Καλημέρα",
      "english": "Good morning",
      "audioUrl": "gs://public-assets-bucket/audio/kalimera.mp3"
    }
  ],
  "exercises": [
    {
      "type": "slang_matcher",
      "prompt": "Match the formal phrase to its street equivalent.",
      "data": {
         "pairs": [
            {"formal": "Τι κάνετε;", "slang": "Τι λέει;"}
         ]
      }
    },
    {
      "type": "image_description",
      "prompt": "Describe what you see in this picture in Greek.",
      "imageUrl": "gs://public-assets-bucket/images/airport_scene.jpg"
    },
    {
      "type": "conversation",
      "prompt": "Listen to the conversation and answer the questions.",
      "data": {
        "topic_description": "Two people discussing directions at the market.",
        "lines": [
          { "speaker": "male", "text": "Συγγνώμη, πού είναι η Ακρόπολη;", "audioUrl": "gs://..." },
          { "speaker": "female", "text": "Πηγαίνετε ευθεία και στρίψτε δεξιά.", "audioUrl": "gs://..." }
        ],
        "checkpoints": [
          {
            "afterLineIndex": 1,
            "question": "What would the male speaker most naturally say next?",
            "options": [
              { "text": "Ευχαριστώ πολύ!", "isCorrect": true },
              { "text": "Δεν καταλαβαίνω.", "isCorrect": false },
              { "text": "Πόσο κάνει;", "isCorrect": false }
            ]
          }
        ]
      }
    }
  ]
}
```

### `users/{userId}/ownWords` (subcollection)
Documents representing Greek words or short phrases the student added themselves.

**Document ID:** `{chapterId}__{normalizedGreek}` (double underscore, Greek is LLM-normalized)

> Access: Read by the owning user (active status required). Written exclusively by the `add-own-word` Cloud Function via Admin SDK.

```json
{
  "greek": "ο δάσκαλος / η δασκάλα",
  "english": "teacher",
  "audioUrl": "gs://public-assets-bucket/users/{userId}/own_words/b1_c01_airport__o_daskalos.mp3",
  "chapterId": "b1_c01_airport",
  "bookId": "b1",
  "createdAt": "Timestamp"
}
```

---

### `users/{userId}/favoriteWords` (subcollection)
Documents representing vocabulary words the student has bookmarked for focused practice.

**Document ID:** `{chapterId}__{greek}` (double underscore separator, e.g. `b1_c01_airport__Καλημέρα`)

> Access: Read and write by the owning user only (active status required).

```json
{
  "greek": "Καλημέρα",
  "english": "Good morning",
  "audioUrl": "gs://public-assets-bucket/audio/kalimera.mp3", // Optional
  "chapterId": "b1_c01_airport",
  "bookId": "b1",
  "favoritedAt": "Timestamp"
}
```

---

### `exercise_attempts`
Records of user submissions, primarily used to trigger the backend for grading.

**Document ID:** Auto-generated by Firestore (`addDoc`)

```json
{
  "userId": "{firebase_uid}",
  "chapterId": "chapter_1_airport",
  "exerciseId": "ex_2_describe",
  "type": "image_description", // Must match the exercise definition
  "submittedAt": "Timestamp",
  "payload": {
    // The user's answer
    "text": "Βλέπω ένα αεροπλάνο."
  },
  "status": "pending", // Enum: ["pending", "evaluating", "completed", "error"]
  "evaluation": null // Initially null. Populated by the Cloud Functions backend.
  /*
    When completed:
    "evaluation": {
      "score": 85, // 0-100
      "feedback": "Good job, but you missed the article 'το'.",
      "isCorrect": true // Overall pass/fail
    }
  */
}
```

## 2. Ingestion ZIP Format (`descriptor.json`)

When the LangGraph CLI generates content, it packages it into a `.zip` file. The backend reads this `descriptor.json` to understand what to put in Firestore and where to move the assets.

**Schema of `descriptor.json` inside the ZIP:**

```json
{
  "version": "1.0",
  "action": "create_or_update_chapter",
  "phaseId": "phase_1",
  "chapter": {
     "id": "p1_c1_hotel",
     "curriculumChapterId": "p1_c1",
     "topic": "Hotel Check-in",
     "title": "Check-in Chaos",
     "order": 3,
     "summary": "Your hotel room isn't ready and you need to negotiate with the front desk.",
     "passage_text": "Καλησπέρα, έχω κάνει μία κράτηση...",
     "passageAudioPath": "assets/audio/passage_p1_c1_hotel.mp3",
     "sentenceAudioPaths": [
       "assets/audio/sentence_00_p1_c1_hotel.mp3"
     ],
     "coverImagePath": "assets/images/chapter_cover.jpg",
      "grammarNotes": [
        {
          "heading": "Polite requests with θα ήθελα",
          "explanation": "...",
          "examples": [{ "greek": "Θα ήθελα ένα δωμάτιο.", "english": "I would like a room.", "note": null }],
          "imagePath": "assets/images/grammar_note_00.jpg"
        }
      ],
      "grammarSummary": "## Check-in Chaos\n\n### Grammar: Polite Requests...", // Pre-generated Markdown reference; plain string, no asset paths.
     "vocabulary": [
       {
         "greek": "Ξενοδοχείο",
         "english": "Hotel",
         "audioPath": "assets/audio/xenodoxeio.mp3"
       }
     ],
     "exercises": [
       {
         "type": "image_description",
         "prompt": "Describe the lobby.",
         "imagePath": "assets/images/exercise_image_02.jpg"
       }
     ]
  }
}
```