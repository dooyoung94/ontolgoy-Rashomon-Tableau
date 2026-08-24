from rashomon_tableau.openai_frontend import numbered_context, _extract_output_text


def test_numbered_context_is_deterministic():
    text = "Alpha is related to Beta. Gamma contradicts Delta! Is Epsilon present?"
    assert numbered_context(text) == (
        "[0] Alpha is related to Beta.\n"
        "[1] Gamma contradicts Delta!\n"
        "[2] Is Epsilon present?"
    )


def test_extract_output_text_from_responses_shape():
    raw = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": '{"conflict_detected":true}'}
                ]
            }
        ]
    }
    assert _extract_output_text(raw) == '{"conflict_detected":true}'
