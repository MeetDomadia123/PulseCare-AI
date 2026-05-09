#VoiceBot UI with Gradio
import os
from dotenv import load_dotenv
load_dotenv()
import gradio as gr
import time
import tempfile
import uuid
from fpdf import FPDF
import re
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0

from brain_of_the_doctor import analyze_chat
from voice_of_the_patient import transcribe_with_groq
from voice_of_the_doctor import text_to_speech_with_elevenlabs

system_prompt = """You have to act as a professional doctor, i know you are not but this is for learning purpose. 
            What's in this image?. Do you find anything wrong with it medically? 
            If you make a differential, suggest some remedies for them. Donot add any numbers or special characters in 
            your response. Your response should be in one long paragraph. Also always answer as if you are answering to a real person.
            Donot say 'In the image I see' but say 'With what I see, I think you have ....'
            Dont respond as an AI model in markdown, your answer should mimic that of an actual doctor not an AI bot, 
            Keep your answer concise (max 2 sentences). No preamble, start your answer right away please"""

LANG_CHOICES = [
    "auto", "English", "Hindi", "Gujarati", "Marathi", "Spanish", "French", "German",
    "Italian", "Portuguese", "Arabic", "Bengali", "Tamil", "Telugu", "Urdu",
    "Japanese", "Korean", "Chinese"
]

LANG_TO_CODE = {
    "auto": "auto",
    "English": "en", "Hindi": "hi", "Gujarati": "gu", "Marathi": "mr", "Spanish": "es",
    "French": "fr", "German": "de", "Italian": "it", "Portuguese": "pt", "Arabic": "ar",
    "Bengali": "bn", "Tamil": "ta", "Telugu": "te", "Urdu": "ur", "Japanese": "ja",
    "Korean": "ko", "Chinese": "zh"
}
CODE_TO_LANG = {v: k for k, v in LANG_TO_CODE.items()}

def translate_text(text: str, target_lang_name: str) -> str:
    # reuse the LLM to translate if needed
    return analyze_chat(
        system_prompt=f"Translate to {target_lang_name}. Output only the translation; do not add anything else.",
        history=[],
        user_text=text,
        image_filepath=None,
        model="meta-llama/llama-4-scout-17b-16e-instruct"
    )

def ensure_language(text: str, target_code: str, target_lang_name: str) -> str:
    if target_code == "auto":
        return text
    try:
        detected = detect(text)
    except Exception:
        detected = None
    if detected != target_code:
        return translate_text(text, target_lang_name)
    return text

def process_turn(audio_filepath, text_input, image_filepath, history, last_image, language_choice):
    # accept either mic audio or typed text
    if not audio_filepath and not text_input:
        return history, None, last_image, history, gr.update(value=text_input)

    try:
        if text_input and not audio_filepath:
            stt_text = text_input.strip()
        else:
            stt_text = transcribe_with_groq(
                stt_model="whisper-large-v3",
                audio_filepath=audio_filepath,
                GROQ_API_KEY=os.environ.get("GROQ_API_KEY")
            )

        # Decide target language (auto = detect from user input)
        if language_choice == "auto":
            try:
                target_code = detect(stt_text) or "en"
            except Exception:
                target_code = "en"
            target_lang_name = CODE_TO_LANG.get(target_code, "English")
        else:
            target_lang_name = language_choice
            target_code = LANG_TO_CODE.get(language_choice, "en")

        # Strong instruction to keep the chosen language
        reply_lang_instruction = f"""
Respond strictly in {target_lang_name}. If the user's input is in another language, first infer meaning
but reply only in {target_lang_name}. Do not mix languages. No preamble.
"""

        image_to_use = image_filepath or last_image
        doctor_reply = analyze_chat(
            system_prompt=system_prompt + reply_lang_instruction,
            history=history,
            user_text=stt_text,
            image_filepath=image_to_use,
            model="meta-llama/llama-4-scout-17b-16e-instruct"
        )

        # Fallback: force to target language if model drifted
        doctor_reply = ensure_language(doctor_reply, target_code, target_lang_name)

        new_history = history + [(stt_text, doctor_reply)]
        tts_path = text_to_speech_with_elevenlabs(
            input_text=doctor_reply,
            output_filepath="final.mp3",
            language=target_code  # used to pick an accent-appropriate voice
        )

        new_last_image = image_filepath or last_image
        return new_history, tts_path, new_last_image, new_history, gr.update(value="")

    except Exception as e:
        # Log full traceback server-side for debugging, but show a friendly message to users
        import traceback
        traceback.print_exc()

        user_text = locals().get("stt_text", "")
        friendly = (
            "Sorry — something went wrong while processing your request. Please try again later."
        )
        new_history = history + [(user_text, friendly)]
        return new_history, None, last_image, new_history, gr.update(value="")


def _generate_pdf_from_history(history: list[tuple[str, str]]) -> str:
    """Create a simple PDF from the chat history and return the filepath."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(0, 8, txt="AI Doctor - Visit Report", ln=True, align="C")
    pdf.ln(4)

    def _safe_text(text: str) -> str:
        # Insert spaces into extremely long tokens so FPDF can break lines
        def _chunk_long(match):
            s = match.group(0)
            parts = [s[i:i+80] for i in range(0, len(s), 80)]
            return " ".join(parts)

        # replace any sequence of non-space longer than 80 chars
        return re.sub(r"\S{80,}", _chunk_long, text)

    # maximum cell width = page width minus margins
    cell_w = pdf.w - 2 * pdf.l_margin - 2
    for i, (user, assistant) in enumerate(history, start=1):
        pdf.set_font("Arial", 'B', 11)
        user_text = _safe_text(user)
        user_text = user_text.encode('ascii', 'replace').decode('ascii')
        pdf.multi_cell(cell_w, 6, text=f"Patient: {user_text}")
        pdf.set_font("Arial", size=11)
        assistant_text = _safe_text(assistant)
        assistant_text = assistant_text.encode('ascii', 'replace').decode('ascii')
        pdf.multi_cell(cell_w, 6, text=f"Doctor: {assistant_text}")
        pdf.ln(2)

    tmpdir = tempfile.gettempdir()
    filename = f"visit_report_{uuid.uuid4().hex[:8]}.pdf"
    out_path = f"{tmpdir}/{filename}"
    pdf.output(out_path)
    return out_path


def download_pdf(history: list[tuple[str, str]]):
    """Gradio click handler to generate a PDF and return its filepath for download."""
    if not history:
        return None
    out_path = _generate_pdf_from_history(history)
    return gr.update(value=out_path, visible=True)


def export_json(history: list[tuple[str, str]]):
    """Export the conversation history as a JSON file and return filepath."""
    import json

    if not history:
        history = []
    tmpdir = tempfile.gettempdir()
    filename = f"chat_{uuid.uuid4().hex[:8]}.json"
    out_path = f"{tmpdir}/{filename}"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return gr.update(value=out_path, visible=True)


def process_turn_stream(audio_filepath, text_input, image_filepath, history, last_image, language_choice):
    """Generator that streams partial assistant text to the chat UI."""
    if not audio_filepath and not text_input:
        yield history, None, last_image, history, gr.update(value=text_input)
        return

    try:
        if text_input and not audio_filepath:
            stt_text = text_input.strip()
        else:
            stt_text = transcribe_with_groq(
                stt_model="whisper-large-v3",
                audio_filepath=audio_filepath,
                GROQ_API_KEY=os.environ.get("GROQ_API_KEY")
            )

        if language_choice == "auto":
            try:
                target_code = detect(stt_text) or "en"
            except Exception:
                target_code = "en"
            target_lang_name = CODE_TO_LANG.get(target_code, "English")
        else:
            target_lang_name = language_choice
            target_code = LANG_TO_CODE.get(language_choice, "en")

        reply_lang_instruction = f"""
Respond strictly in {target_lang_name}. If the user's input is in another language, first infer meaning
but reply only in {target_lang_name}. Do not mix languages. No preamble.
"""

        image_to_use = image_filepath or last_image

        # Get full reply first (backend may not support token streaming)
        full_reply = analyze_chat(
            system_prompt=system_prompt + reply_lang_instruction,
            history=history,
            user_text=stt_text,
            image_filepath=image_to_use,
            model="meta-llama/llama-4-scout-17b-16e-instruct"
        )

        # Ensure language
        full_reply = ensure_language(full_reply, target_code, target_lang_name)

        # Stream by chunks to give responsive feel
        chunk_size = 20
        for i in range(chunk_size, len(full_reply) + chunk_size, chunk_size):
            partial = full_reply[:i]
            new_history = history + [(stt_text, partial)]
            yield new_history, None, image_to_use, new_history, gr.update(value="")
            time.sleep(0.04)

        # Once finished, generate tts and return final outputs
        tts_path = text_to_speech_with_elevenlabs(
            input_text=full_reply,
            output_filepath="final.mp3",
            language=target_code
        )

        final_history = history + [(stt_text, full_reply)]
        yield final_history, tts_path, image_to_use, final_history, gr.update(value="")

    except Exception:
        import traceback
        traceback.print_exc()
        user_text = locals().get("stt_text", "")
        friendly = (
            "Sorry — something went wrong while processing your request. Please try again later."
        )
        new_history = history + [(user_text, friendly)]
        yield new_history, None, last_image, new_history, gr.update(value="")

# --- nicer UI ---
nice_theme = gr.themes.Soft(primary_hue="teal", secondary_hue="slate", neutral_hue="gray")

CUSTOM_CSS = """
/* Global readable base font and spacing */
.gradio-container {
  max-width: 1100px !important;
  font-size: 16px;
  padding: 8px;
}

/* Card look */
.card {
  border: 1px solid var(--border-color-primary);
  border-radius: 14px;
  padding: 12px;
}

/* Header */
.header { text-align: center; margin: 8px 0; }
.header h1 { font-size: 28px; margin: 6px 0; }
.header p { color: var(--body-text-color-subdued); margin: 0; }

/* Chat readability */
#chatbot .wrap .message { font-size: 18px; line-height: 1.5; }

/* Big, easy buttons */
#ask_btn, #clear_btn { height: 56px; font-size: 18px; }

/* Audio components: compact controls (helpful on mobile) */
audio { width: 100%; }

/* Responsive stacking: on small widths, stack columns and expand touch targets */
@media (max-width: 820px) {
  .gradio-container { font-size: 17px; }
  #chatbot { height: 480px !important; }
  .header h1 { font-size: 24px; }
  .header p { font-size: 15px; }
  #ask_btn, #clear_btn { height: 60px; font-size: 19px; }

  /* Stack the input columns vertically */
  .responsive-row .gr-column { width: 100% !important; }
}

/* Extra-small phones */
@media (max-width: 420px) {
  .gradio-container { font-size: 18px; }
  #chatbot { height: 520px !important; }
  #ask_btn, #clear_btn { height: 64px; font-size: 20px; }
}
"""

with gr.Blocks(title="AI Doctor – Voice & Vision", theme=nice_theme, css=CUSTOM_CSS) as iface:
    gr.Markdown(
        """
        <div class="header">
          <h1>👨‍⚕️ AI Doctor</h1>
          <p>Speak or type your concern. Optionally add a photo. Ask follow‑ups; the doctor remembers.</p>
        </div>
        """
    )

    history_state = gr.State([])   # list[(user, assistant)]
    image_state = gr.State(None)   # remember last image

    # Add a class so CSS can stack this row on small screens
    with gr.Row(equal_height=True, elem_classes=["responsive-row"]):
        with gr.Column(scale=5, elem_classes=["card"]):
            audio_in = gr.Audio(
                sources=["microphone"], type="filepath", label="Speak",
                show_download_button=False
            )
            text_in = gr.Textbox(
                lines=2, placeholder="Or type your question here…",
                label="Type instead of speaking"
            )
        with gr.Column(scale=5, elem_classes=["card"]):
            image_in = gr.Image(type="filepath", label="Optional image")
        with gr.Column(scale=2, elem_classes=["card"]):
            language_dd = gr.Dropdown(
                choices=LANG_CHOICES, value="auto", label="Language"
            )
            gr.Markdown("Auto will match your speech; or pick a language to force it.")

    with gr.Row():
        submit = gr.Button("🎤 Ask Doctor", variant="primary", elem_id="ask_btn")
        clear = gr.Button("🧹 Start New Visit", variant="secondary", elem_id="clear_btn")
        clear_img = gr.Button("🖼️ Clear Image", variant="secondary", elem_id="clear_img_btn")

    chat = gr.Chatbot(label="Conversation", elem_id="chatbot", height=420)
    tts_out = gr.Audio(type="filepath", label="Doctor Audio", show_download_button=True)

    # Use streaming handler to improve responsiveness
    submit.click(
        fn=process_turn_stream,
        inputs=[audio_in, text_in, image_in, history_state, image_state, language_dd],
        outputs=[chat, tts_out, image_state, history_state, text_in]
    )

    def _clear_image():
        return None, gr.update(value=None)
    # clear_img updates image_state and clears the image input control
    clear_img.click(fn=_clear_image, inputs=None, outputs=[image_state, image_in])

    def _clear():
        return [], None, None, [], ""
    clear.click(_clear, inputs=None, outputs=[chat, tts_out, image_state, history_state, text_in])

    # Quick-prompt chips for ease of use
    with gr.Row():
        gr.Markdown("Quick prompts:")
        b1 = gr.Button("I fell and my wrist hurts")
        b2 = gr.Button("I have a persistent cough")
        b3 = gr.Button("Skin rash and itching")

    b1.click(lambda: "I fell and my wrist hurts", None, text_in, queue=False)
    b2.click(lambda: "I have a persistent cough", None, text_in, queue=False)
    b3.click(lambda: "Skin rash and itching", None, text_in, queue=False)

    # Export buttons: PDF report and JSON conversation export
    with gr.Row():
        pdf_btn = gr.Button("Download Report (PDF)")
        json_btn = gr.Button("Export Conversation (JSON)")
        pdf_out = gr.File(label="Report PDF", visible=False)
        json_out = gr.File(label="Conversation JSON", visible=False)

    pdf_btn.click(fn=download_pdf, inputs=[history_state], outputs=[pdf_out])
    json_btn.click(fn=export_json, inputs=[history_state], outputs=[json_out])

if __name__ == "__main__":
    iface.launch(debug=True, share=True)

    # To run on a remote server bind to all interfaces and a port:
    # iface.launch(server_name="0.0.0.0", server_port=7860, debug=True, share=True)
