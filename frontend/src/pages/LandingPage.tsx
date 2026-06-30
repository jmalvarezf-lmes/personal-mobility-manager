import Nav from "../components/Nav";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Nav />
      <main className="flex flex-col items-center justify-center py-24">
        <h1 className="text-4xl font-bold text-gray-800">
          Personal Mobility Manager
        </h1>
      </main>
    </div>
  );
}
