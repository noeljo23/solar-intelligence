import { api } from "@/lib/api";
import { CountryHeader } from "@/components/country-header";
import { ChatBox } from "@/components/chat-box";

export default async function ChatPage({ params }: { params: { name: string } }) {
  const name = decodeURIComponent(params.name);
  const profile = await api.country(name);

  const stateNames = profile.states.map((s) => s.name);

  return (
    <div className="flex flex-col min-h-[70vh]">
      <CountryHeader profile={profile} />
      <div className="flex flex-col flex-1 min-h-[60vh]">
        <ChatBox country={profile.name} stateNames={stateNames} />
      </div>
    </div>
  );
}
