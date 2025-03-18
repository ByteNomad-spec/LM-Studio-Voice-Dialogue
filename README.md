🗣️ **LM-Studio-Voice-Dialogue**

LM-Studio-Voice-Dialogue is an application for voice dialogue with artificial intelligence via a local Lm studio server. It includes speech synthesis (TTS), speech recognition (ASR) functions, and support for multitasking communication.  
The application works using **Whisper** and **Coqui TTS** models to enhance text and audio processing.

🚀 **Main Components**

🔧 **Loading and saving settings/history** 
- The **`load_settings` and `save_settings`** functions load and save settings in JSON files. 
- The conversation history and message counter (Needed for the "long-term memory" mechanism) are stored separately to maintain context between launches.

📝 **Spell Checking**  
- **SpellCheckHighlighter** and **SpellCheckTextEdit** work with **pyenchant** to highlight text errors.  
- Incorrect words can be corrected with a single click.

🎙️ **Asynchronous Speech Synthesis (TTS)**  
- **AssistantMessageWorker** splits the text into parts, synthesizes the speech, and plays it sequentially.

### 🧠 **AI Assistant Logic**  
- Audio recording via **pyaudio**.  
- Speech recognition with **Whisper**.  
- Response generation via **OpenAI API**.  
- Notifications played using **pygame.mixer**.

🖥️ **Graphical Interface (GUI) with PyQt6**  
- The settings window allows modifying the application parameters, as well as the palette for all interface elements.  
- The main window includes a chat, input field, and control buttons (record, send, speak, etc.).

🏗️ **Long-Term Memory Logic**  
- The entire process happens cyclically and hidden, without interrupting the dialogue. After a certain number of messages (`summary_interval`), which can be adjusted in settings (e.g., for 8192 tokens, I recommend 8), **generate_summary** is called, passing instructions to the AI to create a concise, structured summary of all key information.  
- Since the summary of key information is created cyclically, all important data will always be within the AI context length, serving as the AI's long-term memory.  
- This helps the AI retain key information even with limited context.

🛠️ **Requirements**  
- **Recommend gemma 2 9b it Q4_K_M**  
- **Python 3.10.0**  
- **FFmpeg** (needed for audio processing)  
- Install dependencies:  

```bash
pip install -r requirements.txt
```

🔹 **Additional**  
If you use the Russian language for spell checking, add the files **ru_RU.aff** and **ru_RU.dic** to:  
`Lib\site-packages\enchant\data\mingw64\share\enchant\hunspell`

📦 **Installation**

1. **Clone the repository**:  

```bash
git clone https://github.com/ByteNomad-spec/LM-Studio-Voice-Dialogue.git
cd LM-Studio-Voice-Dialogue
```

2. **Install dependencies**:  

```bash
pip install -r requirements.txt
```

3. **Set up FFmpeg**:  
   - Make sure **FFmpeg** is installed.  
   - For Windows, download it [here](https://ffmpeg.org/download.html) and add it to PATH.

4. **Add spell check files (if using Russian)**:  
   - Download **ru_RU.aff** and **ru_RU.dic**.  
   - Place them in `Lib\site-packages\enchant\data\mingw64\share\enchant\hunspell`.

▶️ **Usage**

1. Run the application (after launching Lm Studio, enabling the server, and starting the desired AI model):  

```bash
python En_language.py  # for English  
python Ru_language.py  # for Russian  
```

👨‍💻 **Developer**

This project was created as a hobby. I am not a professional programmer — my main job is in a completely different field. However, I was curious to implement this idea and experiment with artificial intelligence.  
The project is mostly written using the ChatGPT model (specifically, o3 Mini). I interacted with it, tested it, provided feedback, and made adjustments.  
The code is open for anyone who wants to improve or use it in their own projects.

☕ **Coffee Donations**

If you liked the project and want to support my experiments, you can send a small donation:  

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
