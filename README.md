🗣️ **LM-Studio-Voice-Dialogue**

![LM Studio Voice Dialogue](media/screenshot.png)

## Overview

LM-Studio-Voice-Dialogue is an application that enables voice interaction with artificial intelligence through a local LM Studio server. It incorporates speech recognition (ASR) and speech synthesis (TTS). The system uses Whisper for speech-to-text transcription, Coqui TTS for high-quality text-to-speech synthesis, and a local OpenAI ChatCompletion API to generate responses.

---

## 🚀 Main Components

### 🔧 Settings and History Management
- The `load_settings` and `save_settings` functions are responsible for managing configurations stored in `settings.json`.  
- The system stores the conversation history in `conversation_history.json` and maintains a separate `message_counter.json` to preserve context between sessions and support a long-term memory mechanism.

### 📝 Spell Checking
- **SpellCheckHighlighter** and **SpellCheckTextEdit** integrate with **pyenchant** to highlight spelling errors in real time.
- Misspelled words are underlined and can be corrected via a context menu when clicked.

### 🎙️ Synchronous Display of Speech and Text (TTS)
- **AssistantMessageWorker** divides the assistant’s response into sentences and synthesizes audio for each sentence using the Coqui TTS model.
- During audio playback, the corresponding text is gradually displayed with a delay proportional to the audio duration.
- This approach ensures long responses are vocalized without delay while synchronizing text display with speech playback.

### 🧠 AI Assistant Logic
- **Audio Input & Output:**  
  - Audio is recorded using **PyAudio** and played back using **pygame.mixer**.  
  - **Whisper** is employed to transcribe recorded audio into text.
- **Response Generation:**  
  - User messages (typed or transcribed) are sent to a local OpenAI ChatCompletion API (configured at `http://localhost:1234/v1`) using the model `"local-model"`.
  - The conversation history is updated with both user and assistant messages.
- **Long-Term Memory:**  
  - A message counter tracks the number of exchanges, and upon reaching a configurable threshold (`summary_interval`), the **generate_summary** method is called.
  - This method produces a concise, structured summary of key information about the user and the conversation, ensuring essential details remain within the AI’s context window.

### 🖥️ Graphical User Interface (GUI) with PyQt6
- The application features a modern, user-friendly interface built with **PyQt6**, divided into three main panels:
  - **Input Panel:** Contains a text input field (with live spell checking) and a “Send” button.
  - **Chat Panel:** Displays the conversation history with color-coded labels for User, Assistant, and System messages.
  - **Control Panel:** Provides controls for recording audio, stopping or canceling recordings, updating the voice sample, halting speech synthesis, and accessing settings.
- **Settings Window:**  
  - Allows customization of parameters such as text size, TTS model, Whisper model, summary interval, assigning hot keys and color themes.
  - Changes are saved to a JSON file; some (e.g., font size) take effect immediately, while others require a restart.

### 🏗️ Long-Term Memory Logic
- The entire process runs cyclically and covertly, without interrupting the dialogue. After a certain number of messages (defined by `summary_interval`, which can be configured in the settings — for example, for 8192 tokens, I recommend 8), the **generate_summary** function is invoked, passing instructions to the AI to create a brief, structured summary of all the key information using a template and a prioritized list. Initially, there may be some issues.
- Since the summary of key information is generated cyclically, all important data will always remain within the AI's context window, effectively functioning as long-term memory.
- This mechanism helps the AI retain key information even with a limited context.

---

## ⚙️ Requirements

- **Python 3.10.0** (or a compatible version)
- **FFmpeg** (required for audio processing—ensure it is installed and added to your PATH)
- **PyAudio, pygame, whisper, Coqui TTS, PyQt6, openai, torch, pyenchant** and other dependencies listed in `requirements.txt`.

### 🔹 Additional
- For Russian spell checking support, add the **ru_RU.aff** and **ru_RU.dic** files to:
  ```
  Lib\site-packages\enchant\data\mingw64\share\enchant\hunspell
  ```

---

## 🛠️ Installation

### 1. Install Git (If Not Already Installed)  
Before cloning the repository, press the `Win + R` keys simultaneously.  
In the run dialog that appears, type `cmd` and press **Enter**, 
check if Git is installed by running:

```bash
git --version
```

If you see an error or no version information, install Git by opening Command Prompt or PowerShell **as an Administrator** and running:

```bash
winget install --id Git.Git -e --source winget
```

---

### 2. Clone the Repository

   ```bash
   git clone https://github.com/ByteNomad-spec/LM-Studio-Voice-Dialogue.git
   cd LM-Studio-Voice-Dialogue
   ```

---

### 3. (Optional) Create a Python Virtual Environment  
Creating an isolated environment is recommended to avoid dependency conflicts with other projects. This step is optional.

1. **Inside the Repository Folder:**  
   Create a virtual environment named `env` by running:
   ```bash
   python -m venv env
   ```
2. **Activate the Virtual Environment (Windows):**
   ```bash
   env\Scripts\activate
   ```
   Your terminal prompt will change to show that you are now operating within the virtual environment.

---

### 4. Install Dependencies  
With your virtual environment activated—or directly in the repository folder if you skipped the environment step—install the required packages:

```bash
pip install -r requirements.txt
```

*Note:* Both the English and Russian versions share the same dependencies.

---

### 5. Set Up FFmpeg  
FFmpeg is required for audio processing. Follow these steps:

- **Download FFmpeg:**  
  Visit [https://ffmpeg.org](https://ffmpeg.org) and download the Windows version (usually provided as a ZIP archive).

- **Extract the Archive:**  
  Extract the contents to a convenient location such as `C:\ffmpeg`.

- **Add FFmpeg to PATH:**  
1. Open **Control Panel** → **System** → **Advanced system settings**.
2. Click on **Environment Variables**.
3. In the "System variables" section, locate and select the `Path` variable, then click **Edit**.
4. Add the full path to the `bin` folder within your FFmpeg directory (e.g., `C:\ffmpeg\bin`).

- **Verify the Installation:**  
  Open a new Command Prompt window and run:
  ```bash
  ffmpeg -version
  ```
  This should display FFmpeg’s version details if the setup is correct.

---

### 6. Add Spell Check Files (For the Russian Version Only)  
If you are using the Russian version of the program, perform these additional steps:

1. **Download the Files:**  
   Obtain the spell check files `ru_RU.aff` and `ru_RU.dic`.

2. **Place the Files:**  
   Copy both files into the following directory within your project’s virtual environment:
   ```
   LM_Studio_Voice_Dialogue_RU\env\Lib\site-packages\enchant\data\mingw64\share\enchant\hunspell
   ```

---

## ▶️ Usage

1. Launch the application (after starting LM Studio, enabling the local server, and loading the desired AI model):

   ```bash
   python En_language.py  # for English
   python Ru_language.py  # for Russian
   ```

---

## 👨‍💻 Developer

This project was created as a hobby. I am not a professional programmer—my primary career is in a different field. I developed this application out of curiosity and a desire to experiment with artificial intelligence and voice interaction.  
The project is open to anyone interested in improving or adapting it for their own purposes.

---

## ☕ Coffee Donations

If you appreciate the project and would like to support my experiments, you can send a small donation:

**Bitcoin:** `bc1q0jzxrafdq5wn4yerfx5w5sckupepwn9ts2dxwp`

---

## 📜 License

This project uses the following libraries and models:

- **Whisper (ASR)** — licensed under the [MIT License](https://opensource.org/licenses/MIT).
- **Coqui TTS (TTS)** — licensed under the [Coqui Public Model License 1.0.0](https://github.com/coqui-ai/TTS/blob/main/LICENSE).
- **PyTorch** — licensed under the [BSD License](https://opensource.org/licenses/BSD-3-Clause).
- **torchvision** — licensed under the [BSD License](https://opensource.org/licenses/BSD-3-Clause).
- **torchaudio** — licensed under the [BSD License](https://opensource.org/licenses/BSD-3-Clause).
- **FFmpeg** — licensed under [LGPLv2.1](https://www.ffmpeg.org/legal.html) or [GPLv3](https://www.ffmpeg.org/legal.html), depending on the build.
- **pyenchant** — licensed under the [LGPL License](https://opensource.org/licenses/LGPL-3.0).
- **PyQt6** — licensed under the [GPL v3 License](https://www.gnu.org/licenses/gpl-3.0.html) or a commercial license. 

Please ensure you comply with the terms of these licenses before using the project.
```
