from litellm import acompletion
import json
import os
import asyncio

async def stream_response():
    try:
        # Initialize the completion request
        response = await acompletion(
            # litellm picks its client (OpenAI-style, Anthropic-style, ...) from
            # a prefix on the model name, not from api_base alone — mkp-api is an
            # OpenAI-compatible /chat/completions endpoint, hence "openai/".
            model="openai/gemma-4-31B-it",
            api_base="https://mkp-api.fptcloud.com",    # Base URL for API
            api_key=os.environ["FPT_CLOUD_API_KEY"],    # set this in your shell, don't hardcode a real key here
            messages=[                    # List of message objects. Please update the System prompt to have the model respond appropriately
                {
                    "role": "system",
                    "content": "You are a helpful assistant capable of understanding a user's needs through conversation to recommend suitable services. Based on the conversation history and the user's last message, list services that can address the user's needs. Respond only in Vietnamese or English, matching the language of the user's input."
                },
                {
                    "role": "user",
                    "content": "hi"
                }
            ],
            stream=True  # Enable streaming
        )
        # Process streaming response
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield f"data: {json.dumps({'content': chunk.choices[0].delta.content})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    yield "data: [DONE]\n\n"

async def main():
    async for data in stream_response():
        print(data)

if __name__ == '__main__':
    asyncio.run(main())