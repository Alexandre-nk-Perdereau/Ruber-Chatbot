# Ruber Chatbot

This is a Discord chatbot powered by Google's Gemini API, designed to interact with users in text channels and process various types of attachments.

## Features

*   **Conversational AI:** Engages in natural language conversations with users.
*   **Context Awareness:** Maintains context throughout the conversation using a custom context management system.
*   **Multimedia Support:** Processes and understands text, images (converted to PNG), audio, and MP4 video attachments.
*   **Gemini API Integration:** Leverages the power of the Gemini API for text generation, image generation, and model information retrieval.
*   **Configurable:** Allows setting the system prompt, context size, and the Gemini model used per channel.
*   **Command Handling:** Supports several commands for interaction and management, including activation, deactivation, context clearing, context downloading, and model listing.

## Project Structure

This chatbot is structured into several modules:

*   `main.py`: The entry point for the chatbot. It initializes and runs the bot.
*   `bot/bot.py`: Contains the main logic for the chatbot, including command handling and message processing.
*   `utils/config.py`: Handles configuration settings, such as API keys and default prompts.
*   `utils/context.py`: Manages the conversational context for each channel.
*   `utils/gemini.py`: Provides functions for interacting with the Gemini API.
*   `start_bot.sh`: Script to start the chatbot.
*   `stop_bot.sh`: Script to stop the chatbot.

## Setup

1. **Environment:**
    *   Ensure Python 3.9+ is installed.
    *   Create and activate a virtual environment:

        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        ```

2. **Dependencies:**
    *   Install the required Python packages:

        ```bash
        pip install -r requirements.txt
        ```
        *Content of `requirements.txt`:*
        ```text
        discord.py
        python-dotenv
        google-generativeai
        Pillow
        aiohttp
        ```

3. **Configuration:**
    *   Create a `.env` file in the root directory.
    *   Add your Discord bot token, Gemini API key, and other configurations to the `.env` file:

        ```
        DISCORD_BOT_TOKEN=your_discord_bot_token
        GEMINI_API_KEY=your_gemini_api_key
        DEFAULT_MODEL=gemini-2.0-flash-exp
        DEFAULT_CONTEXT_SIZE=2097152
        DEFAULT_SYSTEM_PROMPT="You are Ruber, a helpful and friendly chatbot."
        ```
        **Note:** Adjust the `DEFAULT_MODEL`, `DEFAULT_CONTEXT_SIZE`, and `DEFAULT_SYSTEM_PROMPT` to your desired values.

## Running the Chatbot

1. **Start the bot:**

    ```bash
    ./start_bot.sh
    ```

2. **Stop the bot:**

    ```bash
    ./stop_bot.sh
    ```

## Usage

### Commands

*   `/activer`: Activates the chatbot in the current channel.
*   `/desactiver`: Deactivates the chatbot in the current channel.
*   `/clear`: Clears the conversation context for the current channel.
*   `/download`: Downloads the conversation context for the current channel as a text file.
*   `/set_system_prompt <new_system_prompt>`: Sets a new system prompt for the current channel.
*   `/set_context_size <new_context_size>`: Sets the maximum context size (in tokens) for the current channel.
*   `/set_model <new_model>`: Sets the Gemini model to be used for the current channel.
*   `/info`: Displays the current settings (system prompt, model, context size) for the current channel.
*   `/debug_listmodels`: Lists the available Gemini models and their supported methods.

The imagen command doesn't work yet, waiting the integration of imagen3 in gemini API.

### Interactions

*   The chatbot will respond to messages in channels where it has been activated using the `/activer` command.
*   It can process text, images, audio files, and MP4 videos sent as attachments.
*   The chatbot maintains context within each channel, allowing for more natural conversations.

## Notes

*   The chatbot uses a file named `activated_channels.json` to store the list of channels where it is active.
*   Conversation contexts are stored in the `contexts` directory.
*   Some gemini models can induce RC500 errors (especially gemini experimental 1206 in my experience).

You can use this code freely in your own projects without any restrictions.