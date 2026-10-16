# Execução semanal local

A rotina usa os plugins GitHub/GitLab já autenticados no Codex. O Mac deve estar ligado e acordado, com o Codex disponível no horário. Ela não usa ambiente cloud, não publica relatórios e não instala nada a cada execução.

## Preparação única

1. Instale Node.js 20+, Python 3.10+ (com fusos IANA) e Google Chrome.
2. Na pasta do template, execute `npm ci` uma vez.
3. Conecte GitHub e GitLab no Codex, autorizando os repositórios que deseja consultar.
4. Execute a demonstração abaixo. Para atribuição por e-mail, confira o Git local e os aliases opcionais de `collector/config.example.json`, copiados para uma pasta privada.

```sh
npm run weekly -- --demo --output-dir ../weekly-reports --state-dir ../private-run
```

O nome do arquivo começa com `demo-`, e a imagem indica “Dados fictícios”. O teste não consulta integrações.

## Rotina real

Dentro de uma sessão do Codex:

```sh
npm run weekly -- --output-dir ../weekly-reports --state-dir ../private-run
```

O agente atende aos pedidos de leitura de `collector/bridge.py` pelo driver `collector/codex_bridge.js`. O restante é executado pelos scripts: segunda-feira às 00h até o início da rodada, métricas, resumos extrativos, renderização e limpeza.

- `--config ../private-run/config.local.json`: aliases e filtros privados opcionais.
- `--end '2026-10-16T21:00:00-03:00'`: corte explícito; a semana continua começando na segunda-feira.
- `--channel chrome`: padrão; usa o Chrome instalado.
- `--channel chromium`: alternativa para um Chromium previamente instalado via Playwright.

Somente o PNG é preservado. O JSON, a auditoria em memória e o cache dos conectores são temporários. Fica um pequeno arquivo de bloqueio em `--state-dir` para impedir execuções simultâneas. Cada PNG tem data/hora e permissões privadas; arquivos existentes não são sobrescritos. Uma fonte indisponível nunca significa zero atividade. Se ambas falharem, não se gera relatório.

## Agendamento no Codex

Peça uma tarefa local semanal, por exemplo sexta-feira às 21h em America/Sao_Paulo, contendo estas instruções:

> Execute `python3 -m collector.weekly` no diretório do template, com pastas privadas externas para estado e PNGs. Atenda à ponte anunciada na saída conforme `collector/BRIDGE.md`, usando somente os plugins GitHub/GitLab de leitura. Não instale pacotes nem navegadores. Use os resumos extrativos produzidos pelo coletor, sem análise extensa. Depois do sucesso, apresente apenas “Resumo Semanal de Projetos”, o período e a imagem PNG pelo caminho absoluto. Avise brevemente se a cobertura estiver incompleta. Não publique nem altere repositórios.

Os caminhos privados específicos da máquina pertencem à configuração do agendamento, não ao repositório público. O template não cria uma automação ao ser instalado.

## Cron do sistema e consumo de tokens

Um cron puro não herda os plugins de uma sessão do Codex. Para manter os plugins, use o agendamento local do Codex. Essa execução ainda consome tokens do agente, mas os scripts fazem os cálculos, os resumos extrativos e a exportação, sem chamadas a modelos de IA.

Uma versão independente de agente precisaria de um transporte direto às APIs e autenticação de leitura própria, não implementados neste template. Não copie tokens dos conectores. O relatório deste modo é um arquivo local; sua apresentação automática neste chat depende da tarefa do Codex.

O Chrome pode se atualizar e alterar pequenos detalhes de rasterização. O HTML, CSS, ícones e organização visual do dashboard permanecem os mesmos.
