import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Comparador } from "./pages/Comparador";
import { Produtos } from "./pages/Produtos";

const Soon = ({ title }: { title: string }) => (
  <div className="py-16 text-center">
    <h1 className="text-lg font-semibold">{title}</h1>
    <p className="mt-1 text-sm text-muted">Disponível em breve.</p>
  </div>
);

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Comparador />} />
        <Route path="/produtos" element={<Produtos />} />
        <Route path="/configuracoes" element={<Soon title="Configurações" />} />
        <Route path="/mercado" element={<Soon title="Mercado" />} />
        <Route path="*" element={<Soon title="Página não encontrada" />} />
      </Routes>
    </Layout>
  );
}
