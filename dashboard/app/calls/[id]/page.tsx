import CallDetail from "@/components/CallDetail";

export default async function CallPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CallDetail id={id} />;
}
