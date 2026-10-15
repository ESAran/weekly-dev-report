# Preparação para publicação — registro da fase 3

Este documento registra a revisão anterior à publicação. As pendências e referências a uma publicação futura descrevem aquele momento. Para a instalação e o uso atuais, consulte o README.

Esta pasta é a unidade de distribuição do Weekly Dev Report. Não publique a pasta de trabalho que a contém. A preparação não cria repositório remoto, não faz push e não configura execução recorrente.

## Conteúdo público e configuração privada

- `data/demo.json` e `demo.png` são fictícios; a imagem não contém metadados pessoais.
- `collector/config.example.json` não contém identidades ou repositórios pessoais. Copie-o para fora do projeto e ajuste a cópia privada.
- A autenticação pertence aos conectores do Codex. Não há tokens distribuídos e não é necessário um `.env`.
- O coletor rejeita destinos de relatório e cache dentro do template. O servidor local oferece apenas arquivos de apresentação e JSONs permitidos em `data/`; bloqueia configurações privadas, arquivos ocultos e links simbólicos para fora do projeto.
- O `.gitignore` cobre credenciais, `.env`, configurações locais, dependências, caches, logs e nomes de saídas reais. Em `data/`, apenas `demo.json` é incluído por padrão.
- `package.json` mantém `private: true` para evitar publicação acidental no npm; isso não impede um repositório público no GitHub.

## Revisão de segurança desta distribuição

Foram examinados os arquivos distribuídos em busca de tokens GitHub/GitLab, chaves privadas, credenciais em URLs, identificadores pessoais conhecidos e caminhos absolutos do computador original. Não foram encontrados esses sinais. Os exemplos e testes utilizam dados sintéticos. Foram conferidos também os membros do ZIP: sem dependências instaladas, relatórios reais, caches, configuração privada ou metadados Git.

Não existe `.git` no projeto nem repositório Git nos diretórios pais examinados. Portanto, **não há histórico local a auditar ou sanear**, e o pacote não inclui histórico anterior. Nenhum histórico remoto foi examinado. A conclusão de segurança se aplica somente aos arquivos desta distribuição; uma busca por padrões não garante detectar todo segredo possível.

Se, na publicação futura, for usado um repositório que já tenha commits, revise todas as branches e tags desse destino antes do push. Remover um arquivo ou adicioná-lo ao `.gitignore` não apaga versões antigas. Se houver um segredo real registrado, revogue-o e saneie o histórico antes de publicar. Um histórico anterior não revisado não está coberto por esta validação.

## Procedimento futuro como GitHub Template

1. Escolher a licença do código. MIT foi proposta e ainda depende da confirmação do autor; o arquivo `LICENSE` não foi adicionado.
2. Usar somente os arquivos desta pasta ou do ZIP de distribuição, sem copiar relatórios privados ou caches do ambiente de desenvolvimento.
3. Após autorização para criar/publicar o repositório, revisar os arquivos preparados para o primeiro commit e qualquer histórico preexistente.
4. Publicar e habilitar a opção **Template repository** nas configurações do repositório no GitHub.
5. Validar o fluxo **Use this template** em uma cópia nova. Instalação, demonstração e PNG já foram testados a partir de uma cópia limpa local; a criação via GitHub depende da publicação futura.

Não há workflow de GitHub Actions, cron, webhook ou automação do Codex incluído. A execução semanal é uma etapa futura.

## Pendências e limites

- Definição da licença antes de apresentar o código como open-source permissivo.
- Publicação e habilitação do GitHub Template, somente mediante solicitação posterior.
- Coleta real depende da sessão do Codex e dos conectores disponíveis para cada usuário; não é um coletor independente com tokens de ambiente.
- Reutilização validada em macOS arm64. Os comandos são portáveis para ambientes POSIX, mas Linux/WSL e outras arquiteturas não foram executados nesta máquina.
