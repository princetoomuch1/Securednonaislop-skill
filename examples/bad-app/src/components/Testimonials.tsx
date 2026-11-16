const testimonials = [
  { name: "Sarah Johnson", title: "CEO at TechFlow", quote: "Launchly revolutionized our seamless workflow!", avatar: "https://i.pravatar.cc/150?img=5" },
  { name: "Michael Chen", title: "CTO at DataSync", quote: "A game-changer for our team.", avatar: "https://randomuser.me/api/portraits/men/32.jpg" },
];

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Launchly",
  aggregateRating: { "@type": "AggregateRating", ratingValue: "4.9", reviewCount: "2847" },
};

export default function Testimonials() {
  return (
    <section>
      <h2>Trusted by 500+ companies worldwide</h2>
      <p>Join 10,000+ happy users · Rated 4.9/5 ★★★★★</p>
      {testimonials.map(t => (
        <div key={t.name}><img src={t.avatar} /><p>{t.quote}</p><b>{t.name}</b>, {t.title}</div>
      ))}
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
    </section>
  );
}
