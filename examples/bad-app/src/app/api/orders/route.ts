import { db } from "@/lib/db";

export async function POST(req: Request) {
  const body = await req.json();
  const order = await db.query(`INSERT INTO orders (user_id, product) VALUES ('${body.userId}', '${body.product}') RETURNING *`);
  const session = await stripe.checkout.sessions.create({
    line_items: [{ price_data: { currency: "usd", unit_amount: body.price, product_data: { name: body.product } }, quantity: body.quantity }],
    mode: "payment",
  });
  const preview = await fetch(body.imageUrl);
  await db.profiles.update(body);
  return Response.json({ order, url: session.url });
}
