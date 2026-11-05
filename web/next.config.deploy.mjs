// Configuração de deploy do frontend do EnadeX. Estende a configuração do repositório (renomeada para
// next.config.repo.mjs no build) sem editá-la:
//   - output 'standalone': imagem pequena e partida rápida (só node + server.js);
//   - compress false: a compressão (brotli/gzip) fica no Traefik, que comprime melhor que o gzip do Node;
//   - poweredByHeader false: não anuncia o servidor.
import base from './next.config.repo.mjs'

const deploy = { output: 'standalone', compress: false, poweredByHeader: false }

export default async function config(phase, contexto) {
  const original = typeof base === 'function' ? await base(phase, contexto) : base
  return { ...original, ...deploy }
}
