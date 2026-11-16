export async function POST(req: Request) {
  const event = await req.json(); // stripe event
  if (event.type === "checkout.session.completed") {
    await markPaid(event.data.object.id);
  }
  return new Response("ok");
}
