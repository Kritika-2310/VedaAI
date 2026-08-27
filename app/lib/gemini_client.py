import os
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
import google.generativeai as genai
from app.lib.prompts import (
    QUESTION_EXTRACTION_PROMPT,
    ANSWER_EXTRACTION_PROMPT,
    MAPPING_PROMPT_TEMPLATE,
    GRADING_PROMPT_TEMPLATE,
)

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

MODEL_NAME = "gemini-3.5-flash-lite"


def _get_model():
    return genai.GenerativeModel(
        MODEL_NAME,
        generation_config={
            "response_mime_type": "application/json",
            "max_output_tokens": 8192,
        },
    )


def _clean_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print("=== RAW GEMINI RESPONSE (failed to parse) ===")
        print(text[:3000])
        print("=== END RAW RESPONSE ===")
        raise


def extract_questions(file_bytes: bytes, mime_type: str) -> list[dict]:
    model = _get_model()
    response = model.generate_content(
        [{"mime_type": mime_type, "data": file_bytes}, QUESTION_EXTRACTION_PROMPT]
    )
    parsed = _clean_json(response.text)
    return parsed.get("questions", [])


def extract_answers(file_bytes: bytes, mime_type: str) -> list[dict]:
    model = _get_model()
    response = model.generate_content(
        [{"mime_type": mime_type, "data": file_bytes}, ANSWER_EXTRACTION_PROMPT]
    )
    parsed = _clean_json(response.text)
    return parsed.get("answers", [])


def map_answers(questions: list[dict], answers: list[dict]) -> dict:
    model = _get_model()
    questions_json = json.dumps(
        [{"number": q["number"], "text": q["text"]} for q in questions], indent=2
    )
    answers_json = json.dumps(
        [
            {"index": i, "labelled_number": a.get("labelled_number"), "text": a["text"]}
            for i, a in enumerate(answers)
        ],
        indent=2,
    )
    prompt = MAPPING_PROMPT_TEMPLATE.format(
        questions_json=questions_json, answers_json=answers_json
    )
    response = model.generate_content(prompt)
    return _clean_json(response.text)


def grade_answer(question_text: str, answer_text: str) -> dict:
    model = _get_model()
    prompt = GRADING_PROMPT_TEMPLATE.format(
        question_text=question_text, answer_text=answer_text or "(no answer provided)"
    )
    response = model.generate_content(prompt)
    return _clean_json(response.text)

_executor = ThreadPoolExecutor(max_workers=4)


async def extract_questions_async(file_bytes: bytes, mime_type: str) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, extract_questions, file_bytes, mime_type)


async def extract_answers_async(file_bytes: bytes, mime_type: str) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, extract_answers, file_bytes, mime_type)


def grade_all(pairs: list[dict]) -> list[dict]:
    """
    pairs: [{"question_number": "1(a)", "question_text": "...", "answer_text": "..."}, ...]
    One API call for the whole paper instead of one per question.
    """
    from app.lib.prompts import BATCH_GRADING_PROMPT_TEMPLATE
    model = _get_model()
    pairs_json = json.dumps(pairs, indent=2)
    prompt = BATCH_GRADING_PROMPT_TEMPLATE.format(pairs_json=pairs_json)
    response = model.generate_content(prompt)
    parsed = _clean_json(response.text)
    return parsed.get("results", [])
