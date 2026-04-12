import { api } from "@/lib/api";
import { CountryHeader } from "@/components/country-header";
import { ChatBox } from "@/components/chat-box";

export default async function ChatPage({ params }: { params: { name: string } }) {
  const name = decodeURIComponent(params.name);
  const profile = await api.country(name);

  const stateNames = profile.states.map((s) => s.name);

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">
      <CountryHeader profile={profile} />
      <ChatBox country={profile.name} stateNames={stateNames} />
    </div>
  );
}
