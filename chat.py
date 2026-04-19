import httpx
import asyncio

async def ask():
    url = "http://127.0.0.1:8000/ask"
    print("--- Llama Chat Terminal (write'exit' to quit ) ---")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ['exit', 'quit', 'logout']:
                break
            
            try:
                response = await client.post(url, json={"prompt": user_input})
                result = response.json()
                
                print(f"\nLlama: {result.get('response')}")
            except Exception as e:
                print(f"\nError: {e}")

if __name__ == "__main__":
    asyncio.run(ask())