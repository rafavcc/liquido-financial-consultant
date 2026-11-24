import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Comparador } from "./pages/Comparador";
import { Configuracoes } from "./pages/Configuracoes";
import { Importar } from "./pages/Importar";
import { Produtos } from "./pages/Produtos";

const Mercado = lazy(() => import("./pages/Mercado").then((m) => ({ default: m.Mercado })));

const Soon = ({ title }: { title: string }) => (
  <div className="py-16 text-center">
    <h1 className="text-lg font-semibold">{title}</h1>
    <p className="mt-1 text-sm text-muted">Disponível em breve.</p>
  </div>
);

export default function App() {
  return (
    <Layout>
      <Suspense fallback={<p className="py-16 text-center text-sm text-muted">Carregando…</p>}>
        <Routes>
          <Route path="/" element={<Comparador />} />
          <Route path="/produtos" element={<Produtos />} />
          <Route path="/importar" element={<Importar />} />
          <Route path="/configuracoes" element={<Configuracoes />} />
          <Route path="/mercado" element={<Mercado />} />
          <Route path="*" element={<Soon title="Página não encontrada" />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}
