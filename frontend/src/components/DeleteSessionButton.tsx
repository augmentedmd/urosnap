import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createPortal } from "react-dom";
import { Trash2 } from "lucide-react";
import { api, type SessionSummary } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Button, Card } from "@/components/ui";

export function DeleteSessionButton({
  session,
  onDeleted,
}: {
  session: SessionSummary;
  onDeleted?: () => void;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [deleteFiles, setDeleteFiles] = useState(false);

  const remove = useMutation({
    mutationFn: () => api.deleteSession(session.public_id, deleteFiles),
    onSuccess: () => {
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["sessions"] });
      qc.invalidateQueries({ queryKey: ["recent-sessions"] });
      qc.removeQueries({ queryKey: ["session", session.public_id] });
      onDeleted?.();
    },
  });

  return (
    <>
      <Button
        size="sm"
        variant="ghost"
        aria-label={`Delete procedure for ${session.patient_name}`}
        title="Delete procedure"
        className="text-[var(--color-danger)] hover:bg-red-50"
        onClick={() => {
          setDeleteFiles(false);
          remove.reset();
          setOpen(true);
        }}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
      {open
        ? createPortal(
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
              role="dialog"
              aria-modal="true"
              onClick={() => !remove.isPending && setOpen(false)}
            >
              <div
                className="w-full max-w-md"
                onClick={(e) => e.stopPropagation()}
              >
                <Card className="space-y-4 p-6 text-left">
                  <h2 className="text-lg font-semibold">
                    Delete this procedure?
                  </h2>
                  <p className="text-sm text-[var(--color-muted)]">
                    {session.patient_name} · {session.display_procedure_name} ·{" "}
                    {formatDate(session.procedure_date)}
                  </p>
                  <p className="text-sm">
                    This removes the procedure, its photos and its reports from
                    the OpenSnap database. This cannot be undone.
                  </p>
                  <label className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4"
                      checked={deleteFiles}
                      onChange={(e) => setDeleteFiles(e.target.checked)}
                    />
                    <span>
                      Also delete the video, photo and PDF files from disk
                    </span>
                  </label>
                  {remove.isError ? (
                    <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">
                      {(remove.error as Error).message}
                    </div>
                  ) : null}
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      onClick={() => setOpen(false)}
                      disabled={remove.isPending}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="danger"
                      onClick={() => remove.mutate()}
                      disabled={remove.isPending}
                    >
                      {remove.isPending ? "Deleting…" : "Delete procedure"}
                    </Button>
                  </div>
                </Card>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
