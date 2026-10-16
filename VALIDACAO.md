# Validação da distribuição — 15 de outubro de 2026

## Instalação limpa

Foi criada uma cópia contendo apenas os arquivos distribuíveis, sem `node_modules`, caches, configuração privada, relatórios reais ou metadados Git. `npm ci` instalou as dependências do lockfile usando um cache novo e reportou zero vulnerabilidades conhecidas naquele momento.

O Chromium Headless Shell e o FFmpeg foram baixados para um diretório novo. A primeira tentativa no diretório de trabalho falhou na atualização do lock do instalador; repetir a instalação em uma pasta temporária local nova concluiu o download. Nenhum navegador previamente instalado foi necessário.

Ambiente validado: macOS arm64, Node.js 22.3.0, Python 3.12, Playwright 1.62.1 e Chromium Headless Shell 151.0.7922.34. Linux/WSL e outras arquiteturas não foram executados.

## Testes executados

- **10 testes JavaScript:** totais, participações, cobertura, empates, dados inválidos, datas, atividade inferior a 1% e segurança HTTP.
- **14 testes Python:** limites de período, autoria, exclusões, merges, importação inicial, diffs truncados, deduplicação por branches/revisões, submódulos, squash/fast-forward, paginação, ponte somente de leitura e evidências dos resumos.
- **Testes visuais:** exportações repetidas determinísticas; 0–4 e 7 projetos; crescimento de altura; nomes e resumos longos; fontes parciais e indisponíveis; participação inferior a 1% em projetos e plataformas; singular “1 linha”; viewport de 390 px sem rolagem horizontal.
- **Acesso HTTP:** arquivos necessários carregam; `.env`, variantes, configuração local, auditoria, relatórios e links simbólicos para fora do projeto são bloqueados.

Todos passaram na cópia limpa. As exportações foram executadas sem variáveis de tokens GitHub/GitLab e sem chamadas autenticadas. Os dados dos testes são sintéticos. As integrações reais não foram reexecutadas nesta etapa; sua validação anterior não garante acesso aos repositórios de outros usuários.

## Design preservado

`index.html`, `styles.css` e `icons.js` mantêm os hashes da versão aprovada. A apresentação JavaScript recebeu apenas os ajustes de rótulo para “<1%” e “1 linha” e da barra para atividade mínima.

O PNG fictício exportado na instalação limpa mede **1.884 × 3.344 px** e é **byte a byte idêntico** ao `demo.png` aprovado:

```text
SHA-256: eda3403d8b9377a8def7bcddad781dcf0211bc3bb0b9bae359ba36f2fea7246d
```

A composição, cores, tipografia, espaçamento e ordem das seções foram preservados. A altura pode crescer com outros dados. Comparações em pixels exigem o mesmo ambiente de rasterização.

## Conferência dos dados fictícios

| Projeto | Adições | Remoções | Volume | Foco | Commits |
| --- | ---: | ---: | ---: | ---: | ---: |
| LLM Benchmark | 354 | 158 | 512 | 41% | 12 |
| Portal Admin | 262 | 129 | 391 | 32% | 9 |
| App Mobile | 154 | 67 | 221 | 18% | 4 |
| Site Institucional | 72 | 37 | 109 | 9% | 2 |
| **Total** | **842** | **391** | **1.233** | **100%** | **27** |

GitHub: 16 commits, 59% dos commits e 733 linhas. GitLab: 11 commits, 41% dos commits e 500 linhas. Esses dados são exclusivamente demonstrativos.

A revisão de privacidade, a ausência de histórico Git local e as pendências de publicação estão em [PUBLICACAO.md](PUBLICACAO.md).

## Execução local simplificada — 16 de outubro de 2026

A rotina `collector.weekly` foi validada com dados fictícios e Google Chrome instalado (155.0.8059.80), sem instalação ou download durante a execução. PNG: 1.884 × 3.344 px. O estado temporário foi removido automaticamente; somente a imagem e o pequeno arquivo de bloqueio foram preservados.

Passaram 18 testes Python, 10 testes JavaScript e a suíte visual com o canal Chrome, incluindo textos longos, baixa atividade e cobertura incompleta. Os quatro novos testes Python verificam bloqueio de execuções simultâneas, proteção do diretório publicável, limpeza em falhas e ausência de um relatório de zeros quando ambas as fontes estão indisponíveis.

HTML, CSS e ícones mantêm os hashes da composição aprovada. A coleta via plugins e as regras de métricas existentes foram preservadas; as integrações reais não foram recolhidas nesta verificação para evitar consultas redundantes. Os resumos da rotina são extrativos, sem uma etapa adicional de interpretação por IA. O Chromium separado permanece como alternativa opcional, previamente instalada, não como requisito do modo local padrão.
