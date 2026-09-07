type SummaryItem = {
  label: string;
  value?: string;
  description: string;
  status?: string;
  tone?: "neutral" | "complete" | "pending";
};

type Props = {
  items: SummaryItem[];
};

function SignalSummaryCards({ items }: Props) {
  return (
    <section className="drct-signal-summary-grid" aria-label="요약 현황">
      {items.map((item) => (
        <article className={`drct-signal-summary-card is-${item.tone ?? "neutral"}`} key={item.label}>
          <span>{item.label}</span>
          <strong aria-label={`${item.label} ${item.value ?? "준비 중"}`}>{item.value ?? "-"}</strong>
          {item.status ? <em>{item.status}</em> : null}
          <p>{item.description}</p>
        </article>
      ))}
    </section>
  );
}

export default SignalSummaryCards;
