import { TopBar } from "../components/TopBar";

/** Document home. The owned/shared lists are built in the next task. */
export function HomePage() {
  return (
    <>
      <TopBar />
      <main className="page-message">Your documents will appear here.</main>
    </>
  );
}
