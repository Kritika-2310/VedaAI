QUESTION_EXTRACTION_PROMPT = """
You are analyzing a scanned/digital question paper. Extract every question in printed order.

Rules:
- Treat labelled sub-parts as SEPARATE entries. "11(a)" and "11(b)" are two entries, not one.
- Preserve original numbering exactly as printed (e.g. "Q3", "11(b)", "2.1").
- For each question, return its bounding box on the page as [ymin, xmin, ymax, xmax] using a
  0-1000 normalized scale (top-left origin).
- If a question spans multiple lines, the bbox should cover the full text block including its
  sub-parts' shared stem if any.
- Include the page number (1-indexed) that this question appears on.

Return STRICT JSON only, no markdown fences, no commentary:
{
  "questions": [
    {"number": "11(a)", "text": "...", "page": 1, "bbox": [120, 50, 180, 900]}
  ]
}
"""

ANSWER_EXTRACTION_PROMPT = """
You are analyzing a scanned handwritten student answer sheet. Identify distinct answer blocks.

Rules:
- Handwriting may be messy; do your best to transcribe it faithfully.
- If the student wrote a question number/label near an answer (e.g. "Q3", "11 b)"), capture it
  as "labelled_number". This may not exactly match official question numbering - capture it as
  written.
- If no number is visible near an answer block, set labelled_number to null.
- An answer may continue onto a later page - just extract each page's block separately with the
  same labelled_number where visible; do not try to merge across pages yourself.
- Return bbox as [ymin, xmin, ymax, xmax] on a 0-1000 normalized scale, per page, top-left origin.
- Include the page number (1-indexed).

Return STRICT JSON only, no markdown fences, no commentary:
{
  "answers": [
    {"labelled_number": "11 b)", "text": "...", "page": 2, "bbox": [200, 40, 340, 950]}
  ]
}
"""

MAPPING_PROMPT_TEMPLATE = """
You are matching student answers to exam questions.

Questions (in printed order):
{questions_json}

Answers found on the answer sheet:
{answers_json}

Rules:
- Match by labelled_number first if it plausibly corresponds to a question number (handle
  handwriting/OCR variance, e.g. "11 b" ~ "11(b)").
- If labelled_number is missing or ambiguous, match by content similarity between the answer
  text and the question text.
- An answer may not correspond to any question in the paper -> list its index in
  "unmatched_answer_indices".
- A question may have NO matching answer -> status "unanswered", empty answer_indices.
- Multiple answer indices can map to one question (multi-page or split answers) -> list them all
  in "answer_indices", in the order they should be read.
- Answers appearing out of the question paper's printed order are still valid matches -> mark
  status "out_of_order" for those, "answered" for in-order matches, "unanswered" for no match.

Return STRICT JSON only, no markdown fences, no commentary:
{{
  "mappings": [
    {{"question_number": "11(a)", "answer_indices": [0, 3], "status": "answered"}}
  ],
  "unmatched_answer_indices": [5]
}}
"""

GRADING_PROMPT_TEMPLATE = """
You are grading a student's answer against the expected question.

Question: {question_text}
Student's answer: {answer_text}

Provide a fair evaluation. If the answer is empty or missing, mark it 0 with feedback noting it
was not attempted.

Return STRICT JSON only, no markdown fences, no commentary:
{{
  "score": 0,
  "max_score": 10,
  "verdict": "correct" | "partially_correct" | "incorrect" | "not_attempted",
  "feedback": "one or two sentence explanation"
}}
"""

BATCH_GRADING_PROMPT_TEMPLATE = """
You are grading a full set of student answers against their exam questions, one API call for
the whole paper.

Pairs to grade (in order):
{pairs_json}

For EACH pair, provide a fair evaluation out of 10. If an answer is empty/missing, score 0 and
note "not attempted" in feedback.

Return STRICT JSON only, no markdown fences, no commentary. The "results" array must have
exactly one entry per input pair, in the same order:
{{
  "results": [
    {{
      "question_number": "1(a)",
      "score": 7,
      "max_score": 10,
      "verdict": "correct" | "partially_correct" | "incorrect" | "not_attempted",
      "feedback": "one or two sentence explanation"
    }}
  ]
}}
"""
