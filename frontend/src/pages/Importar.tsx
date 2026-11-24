import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, ApiError, printUrl } from "../api/client";
import type { ImportBatchView, ImportItemView } from "../api/types";
import { formatDateTime } from "../lib/format";

const POLL_MS = 3000;
const HISTORICO = 5;
const ACCEPT = "image/png,image/jpeg,image/webp";

const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`;

function resultado(i: ImportItemView): string {
  const partes: string[] = [];
  if (i.criados) partes.push(plural(i.criados, "cadastrada", "cadastradas"));
  if (i.renovados) partes.push(plural(i.renovados, "renovada", "renovadas"));
  if (i.ignorados) partes.push(plural(i.ignorados, "ignorada", "ignoradas"));
  return `✓ ${partes.length ? partes.join(" · ") : "nenhuma oferta encontrada"}`;
}

function ItemRow({ item, onRetry, retrying }: { item: ImportItemView; onRetry: (id: string) => void; retrying: boolean }) {
  return (
    <li className="flex items-start gap-3 py-2">
      <a href={printUrl(item.print_id)} target="_blank" rel="noreferrer" className="shrink-0">
        <img src={printUrl(item.print_id)} alt="" loading="lazy" className="h-12 w-12 rounded-lg border border-line object-cover" />
      </a>
      <div className="min-w-0 flex-1 text-sm">
        <div className="truncate font-medium">{item.nome_arquivo}</div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1">
          {item.status === "NA_FILA" && <span className="text-muted">na fila</span>}
          {item.status === "LENDO" && <span className="text-accent">lendo…</span>}
          {item.status === "CONCLUIDO" && <span className="text-pos">{resultado(item)}</span>}
          {item.status === "CONCLUIDO" && item.falhas > 0 && (
            <span className="text-warn">⚠ {plural(item.falhas, "falha", "falhas")}</span>
          )}
          {item.status === "ERRO" && (
            <>
              <span className="text-neg">{item.erro ?? "Erro ao ler o print."}</span>
              <button
                type="button"
                disabled={retrying}
                onClick={() => onRetry(item.id)}
                className="rounded-lg border border-line px-2 py-0.5 text-xs font-medium hover:bg-subtle disabled:opacity-50"
              >
                Tentar de novo
              </button>
            </>
          )}
        </div>
      </div>
    </li>
  );
}

function Batch({ batch, onRetry, retrying }: { batch: ImportBatchView; onRetry: (id: string) => void; retrying: boolean }) {
  const feitos = batch.itens.length - batch.pendentes;
  return (
    <section className="rounded-2xl border border-line bg-surface p-4 shadow-card">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold">Lote de {formatDateTime(batch.criado_em)}</h2>
        <span className="num text-xs text-muted">
          {batch.pendentes > 0 ? `${feitos} de ${batch.itens.length} lidos` : `${plural(batch.itens.length, "print", "prints")}`}
        </span>
      </div>
      <ul className="mt-2 divide-y divide-line">
        {batch.itens.map((i) => (
          <ItemRow key={i.id} item={i} onRetry={onRetry} retrying={retrying} />
        ))}
      </ul>
    </section>
  );
}

export function Importar() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [recusados, setRecusados] = useState<string[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [arrastando, setArrastando] = useState(false);

  const status = useQuery({ queryKey: ["imports", "status"], queryFn: api.imports.status });
  const lotes = useQuery({
    queryKey: ["imports", "list"],
    queryFn: api.imports.list,
    refetchInterval: (q) => (q.state.data?.some((b) => b.pendentes > 0) ? POLL_MS : false),
  });

  const pendentes = (lotes.data ?? []).reduce((n, b) => n + b.pendentes, 0);
  const anterior = useRef(0);
  useEffect(() => {
    if (anterior.current > 0 && pendentes === 0) {
      void qc.invalidateQueries({ queryKey: ["products"] });
      void qc.invalidateQueries({ queryKey: ["simulate"] });
    }
    anterior.current = pendentes;
  }, [pendentes, qc]);

  const upload = useMutation({
    mutationFn: api.imports.upload,
    onSuccess: (r) => {
      setErro(null);
      setRecusados(r.recusados);
      void qc.invalidateQueries({ queryKey: ["imports", "list"] });
    },
    onError: (e) => {
      setRecusados([]);
      setErro(e instanceof ApiError ? e.messages.join(" · ") : "Falha ao enviar os prints.");
    },
  });
  const retry = useMutation({
    mutationFn: api.imports.retry,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["imports", "list"] }),
    onError: (e) => setErro(e instanceof ApiError ? e.messages.join(" · ") : "Falha ao tentar de novo."),
  });

  const configurado = status.data?.configurado === true;
  const enviar = (files: FileList | File[] | null) => {
    const arr = files ? Array.from(files) : [];
    if (arr.length > 0 && configurado) upload.mutate(arr);
    if (inputRef.current) inputRef.current.value = "";
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setArrastando(false);
    enviar(e.dataTransfer.files);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Importar prints</h1>

      {status.isError && (
        <div role="alert" className="rounded-xl border border-line bg-subtle px-4 py-3 text-sm text-neg">
          Não foi possível verificar a importação. Tente recarregar a página.
        </div>
      )}
      {status.data && !status.data.configurado && (
        <div role="alert" className="rounded-xl border border-line bg-subtle px-4 py-3 text-sm">
          <strong>Importação não configurada</strong>
          <p className="mt-0.5 text-muted">Defina LLM_BASE_URL e CASA_LLM_MODEL no servidor para ler prints.</p>
        </div>
      )}
      {status.data?.configurado && status.data.alcancavel === false && (
        <div role="alert" className="rounded-xl border border-line bg-subtle px-4 py-3 text-sm text-warn">
          Servidor LLM indisponível no momento. Os prints entram na fila e são lidos quando ele voltar.
        </div>
      )}

      <label
        onDragOver={(e) => {
          e.preventDefault();
          setArrastando(true);
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={onDrop}
        className={`flex cursor-pointer flex-col items-center gap-1 rounded-2xl border-2 border-dashed px-4 py-8 text-center text-sm transition ${
          arrastando ? "border-accent bg-subtle" : "border-line"
        } ${configurado ? "" : "cursor-not-allowed opacity-60"}`}
      >
        <span className="font-medium">{upload.isPending ? "Enviando…" : "Escolher prints"}</span>
        <span className="text-muted">Toque para abrir a galeria ou arraste os arquivos aqui (PNG, JPEG ou WEBP, até 20 MB cada).</span>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          aria-label="Escolher prints"
          disabled={!configurado || upload.isPending}
          onChange={(e) => enviar(e.target.files)}
          className="sr-only"
        />
      </label>

      {erro && (
        <p role="alert" className="text-sm text-neg">
          {erro}
        </p>
      )}
      {recusados.length > 0 && (
        <div role="status" className="rounded-xl border border-line bg-subtle px-4 py-3 text-sm">
          <div className="font-medium">Arquivos recusados</div>
          <ul className="mt-1 list-disc pl-5 text-muted">
            {recusados.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {lotes.isError && <p className="text-sm text-neg">Não foi possível carregar os lotes.</p>}
      {lotes.data && lotes.data.length === 0 && <p className="py-8 text-center text-sm text-muted">Nenhum lote importado ainda.</p>}
      <div className="space-y-3">
        {(lotes.data ?? []).slice(0, HISTORICO).map((b) => (
          <Batch key={b.id} batch={b} onRetry={(id) => retry.mutate(id)} retrying={retry.isPending} />
        ))}
      </div>
    </div>
  );
}
