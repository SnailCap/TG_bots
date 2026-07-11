import { useStudio } from "../../../app/providers/StudioProvider";
import styles from "./MessagePreview.module.css";

function interpolatePreview(text: string): string {
  return text.replace(/{{\s*([^}]+)\s*}}/g, (_match, variable: string) => `‹${variable.trim()}›`);
}

export function MessagePreview() {
  const studio = useStudio();
  const data = studio.graphSelection?.kind === "node" ? studio.graphSelection.node.data : null;
  const isMessage = data && ["send_message", "ask_input", "choice"].includes(data.kind);

  return (
    <section className={styles.panel} aria-label="Telegram preview">
      <header>Telegram Preview</header>
      <div className={styles.chat}>
        {!isMessage ? (
          <p className={styles.empty}>Select a message, question or choice node.</p>
        ) : (
          <div className={styles.message}>
            {data.mediaPath && <div className={styles.media}>Media · {data.mediaPath.split(/[\\/]/).pop()}</div>}
            <p>{interpolatePreview(data.text || "Empty message")}</p>
            {data.kind === "choice" && data.choices?.length ? (
              <div className={data.keyboard === "reply" ? styles.replyKeyboard : styles.inlineKeyboard}>
                {data.choices.map((choice) => (
                  <button key={choice.id}>{choice.label}</button>
                ))}
              </div>
            ) : null}
            <time>12:34 ✓✓</time>
          </div>
        )}
      </div>
    </section>
  );
}
