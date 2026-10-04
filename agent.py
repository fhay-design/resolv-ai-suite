"""LogiBot – ein einfacher Konsolen-Agent auf Basis des Anthropic SDK."""

import anthropic

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = (
    "Du bist LogiBot, ein freundlicher und hilfsbereiter Assistent. "
    "Antworte klar, präzise und auf Deutsch."
)


def main() -> None:
    # Der Client liest den Schlüssel aus ANTHROPIC_API_KEY
    # (oder einem per `ant auth login` eingerichteten Profil).
    client = anthropic.Anthropic()

    # Kurze Selbstvorstellung
    print("LogiBot: Hallo! Ich bin LogiBot, dein persönlicher Assistent. "
          "Stell mir gerne eine Frage. (Zum Beenden: 'exit' oder 'quit')")

    # Gesprächsverlauf für mehrere Runden
    messages = []

    while True:
        try:
            user_input = input("\nDu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nLogiBot: Bis bald!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "ende"}:
            print("LogiBot: Bis bald!")
            break

        messages.append({"role": "user", "content": user_input})

        # Antwort streamen, damit sie direkt sichtbar wird
        print("LogiBot: ", end="", flush=True)
        answer_parts = []
        with client.messages.stream(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                answer_parts.append(text)
        print()

        # Antwort dem Verlauf hinzufügen
        messages.append({"role": "assistant", "content": "".join(answer_parts)})


if __name__ == "__main__":
    main()
