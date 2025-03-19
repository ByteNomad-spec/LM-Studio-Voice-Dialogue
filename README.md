🗣️ **LM-Studio-Voice-Dialogue**

## Screenshot  
Here is a preview of the LM Studio Voice Dialogue interface:  

![LM Studio Voice Dialogue](media/screenshot.png)

LM-Studio-Voice-Dialogue is an application for voice dialogue with artificial intelligence via a local LM Studio server. It includes speech synthesis (TTS), speech recognition (ASR), and support for multitasking communication. The application uses **Whisper** for speech-to-text transcription and **Coqui TTS** for high-quality speech synthesis, combined with a local OpenAI ChatCompletion API for generating responses.

🚀 **Main Components**

🔧 **Loading and Saving Settings & History**  
- The **`load_settings`** and **`save_settings`** functions manage configuration in JSON files.  
- Conversation history and a separate message counter are stored to maintain context between launches and to support the long-term memory mechanism.

📝 **Spell Checking**  
- **SpellCheckHighlighter** and **SpellCheckTextEdit** integrate with **pyenchant** to highlight spelling errors in real time.  
- Incorrect words are underlined and can be corrected via a context menu (click on the word).

🎙️ **Synchronous Display of Speech and Text (TTS)**
- **AssistantMessageWorker** divides the assistant's response into sentences, then for each sentence synthesizes the corresponding sound using the Coqui TTS model.
- During the playback of the generated audio, the worker simultaneously outputs text characters with a delay calculated in accordance with the audio duration.
- This approach eliminates delay when vocalizing long responses, and the text in the chat interface is displayed synchronously with the speech playback.

### 🧠 **AI Assistant Logic**  
- **Audio Input & Output:**  
  - Audio is recorded using **PyAudio** and played back via **pygame.mixer**.  
  - Whisper is used to transcribe recorded audio into text.  
- **Response Generation:**  
  - User messages (typed or transcribed) are sent to a local OpenAI ChatCompletion API (configured at `http://localhost:1234/v1`) using the model `"local-model"`.  
  - The conversation history is updated with both user and assistant messages.
- **Long-Term Memory:**  
  - A message counter tracks the number of exchanges, and after reaching a configurable threshold (`summary_interval`), the **generate_summary** method is called.  
  - This method generates a concise, structured summary of key information about the user and conversation, which is appended to the conversation history, ensuring that important details are preserved within the AI’s context.

🖥️ **Graphical Interface (GUI) with PyQt6**  
- The application features a modern, user-friendly interface built with **PyQt6**, divided into three main panels:  
  - **Input Panel:** Contains the text input field (with live spell checking) and a “Send” button.  
  - **Chat Panel:** Displays the conversation history with color-coded labels for User, Assistant, and System messages.  
  - **Button Panel:** Provides controls for recording audio, stopping or canceling recordings, updating the voice sample, stopping speech synthesis, and accessing settings.
- **Settings Window:**  
  - Allows customization of parameters such as text size, TTS model, Whisper model, summary interval, and color themes.  
  - All changes are saved to a JSON file, and some changes (like font size) take effect immediately while others require a restart.

🏗️ **Long-Term Memory Logic**  
- The entire process happens cyclically and hidden, without interrupting the dialogue. After a certain number of messages (`summary_interval`), which can be adjusted in settings (e.g., for 8192 tokens, I recommend 7), **generate_summary** is called, passing instructions to the AI to create a concise, structured summary of all key information. There may be some problems at first, you need to tell a little about yourself and ask to remember it for filling out the resume in the future.
- Since the summary of key information is created cyclically, all important data will always be within the AI context length, serving as the AI's long-term memory.  
- This helps the AI retain key information even with limited context.

🛠️ **Requirements**  
- **Python 3.10.0** (or compatible version)  
- **FFmpeg** (needed for audio processing – ensure it is installed and added to PATH)  
- **PyAudio, pygame, whisper, Coqui TTS, PyQt6, openai, torch, pyenchant** and other dependencies as listed in `requirements.txt`.

🔹 **Additional**  
- For Russian spell checking support, add the files **ru_RU.aff** and **ru_RU.dic** to:  
  `Lib\site-packages\enchant\data\mingw64\share\enchant\hunspell`

📦 **Installation**

1. **Clone the repository:**  

   ```bash
   git clone https://github.com/ByteNomad-spec/LM-Studio-Voice-Dialogue.git
   cd LM-Studio-Voice-Dialogue
   ```

2. **Install dependencies:**  

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up FFmpeg:**  
**Download FFmpeg:**
   - Visit the official FFmpeg website: [https://ffmpeg.org](https://ffmpeg.org).
   - Choose the version suitable for Windows. Generally, these are Windows EXE files.

**Extract the Archive:**
   - After downloading the file (which may be a .zip archive), extract it to a convenient location on your computer, for example, `C:\ffmpeg`.

**Add FFmpeg to PATH:**
   - Open the "Control Panel" → "System" → "Advanced system settings".
   - In the "Environment Variables" section, find the `Path` variable and click "Edit".
   - Add the path to the `bin` folder, where the FFmpeg executables are located, for example, `C:\ffmpeg\bin`.

**Verify the Installation:**
   - Open the Command Prompt (Win + R, type `cmd`, and press Enter).
   - Enter the command `ffmpeg -version`. If everything is set up correctly, you will see information about the FFmpeg version.

4. **Add Spell Check Files (if using Russian):**  
   - Download **ru_RU.aff** and **ru_RU.dic**.  
   - Place them in the directory:  
     `Lib\site-packages\enchant\data\mingw64\share\enchant\hunspell`.

▶️ **Usage**

1. Run the application (after launching LM Studio, enabling the local server, and starting the desired AI model):  

   ```bash
   python En_language.py  # for English
   python Ru_language.py  # for Russian
   ```

👨‍💻 **Developer**

This project was created as a hobby. I am not a professional programmer—my main career is in a completely different field. I developed this application out of curiosity and a desire to experiment with artificial intelligence and voice interaction.  
The project is open to anyone interested in improving it or adapting it for their own projects.

☕ **Coffee Donations**

If you like the project and wish to support my experiments, you can send a small donation:  

**Bitcoin:** `bc1q0jzxrafdq5wn4yerfx5w5sckupepwn9ts2dxwp`

📜 **License**

## Licenses

This project uses the following libraries and models:

- **Whisper (ASR)** — licensed under the [MIT License](https://opensource.org/licenses/MIT).
- **Coqui TTS (TTS)** — licensed under the [Coqui Public Model License 1.0.0](https://github.com/coqui-ai/TTS/blob/main/LICENSE).
- **PyTorch** — licensed under the [BSD License](https://opensource.org/licenses/BSD-3-Clause).
- **torchvision** — licensed under the [BSD License](https://opensource.org/licenses/BSD-3-Clause).
- **torchaudio** — licensed under the [BSD License](https://opensource.org/licenses/BSD-3-Clause).
- **FFmpeg** — licensed under [LGPLv2.1](https://www.ffmpeg.org/legal.html) or [GPLv3](https://www.ffmpeg.org/legal.html), depending on the build.
- **pyenchant** — licensed under the [LGPL License](https://opensource.org/licenses/LGPL-3.0).

Please ensure you comply with the terms of these licenses before using the project.
