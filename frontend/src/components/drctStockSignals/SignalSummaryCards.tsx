type SummaryItem = {
  label: string;
  description: string;
};

type Props = {
  items: SummaryItem[];
};

function SignalSummaryCards({ items }: Props) {
  return (
    <section className="drct-signal-summary-grid" aria-label="요약 현황">
      {items.map((item) => (
        <article className="drct-signal-summary-card" key={item.label}>
          <span>{item.label}</span>
          <strong aria-label={`${item.label} 준비 중`}>-</strong>
          <p>{item.description}</p>
        </article>
      ))}
    </section>
  );
}

export default SignalSummaryCards;
