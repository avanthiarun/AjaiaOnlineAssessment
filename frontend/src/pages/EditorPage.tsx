import { useParams } from "react-router-dom";
import { TopBar } from "../components/TopBar";

/** Document editor. The TipTap editor is built in a later task. */
export function EditorPage() {
  const { id } = useParams();
  return (
    <>
      <TopBar />
      <main className="page-message">Editor for document {id} goes here.</main>
    </>
  );
}
