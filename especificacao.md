# Gerenciador de Estado do Codebase - Servidor MCP

## Introdução

Este servidor MCP ajuda qualquer desenvolvedor a gerenciar facilmente o progresso e a evolução de seu projeto criando, atualizando e monitorando um gerenciador de estado para o codebase. Ele fornece contexto suficiente para um Agente de IA de codificação (geralmente um LLM) entender melhor onde estava, onde está agora e como está indo o progresso/desenvolvimento no processo.

Após deixar uma sessão de codificação animada e voltar novamente, você geralmente precisa armazenar informações para fornecer contexto para seu agente na próxima vez. Geralmente, essas informações são armazenadas em arquivos ou bancos de dados, com pouco ou nenhum contexto. Ao usar este servidor MCP, você não precisa se preocupar com o que estava fazendo ou em qual fase/etapa do plano o agente estava da última vez que trabalhou no projeto.

## Como funciona

Este MCP coleta as seguintes informações de qualquer codebase:

    1. Prompt/solicitação do usuário - Todos os prompts do usuário fornecidos para um Agente de IA são salvos no codebase a cada solicitação
    2. `git branch --show-current` - Nome da branch atual
    3. `git diff HEAD~3` - Após as últimas mudanças

A partir dessas informações, a ferramenta gera um hash delas e coloca tudo em uma tupla: 1. Tupla de Estado: <NÚMERO_ESTADO, PROMPT_USUÁRIO, NOME_BRANCH, INFO_GIT_DIFF, HASH>

As transições também são armazenadas em uma tupla: 2. Tupla de Transição: <ID/ÍNDICE, ESTADO_ATUAL, PRÓXIMO_ESTADO, DATA_HORA>

## Definição das Ferramentas

**genesis()** - Inicializa uma máquina de estado para o projeto gerenciado e cria o estado #0 (zero). Cria uma branch chamada 'codebase-state-machine' copiada da branch atual de onde a ferramenta foi chamada. A nova branch será armazenada em um volume dedicado local no contêiner docker. DEVE ser a primeira ferramenta a ser chamada na inicialização do servidor MCP

**new_state_transition(string prompt, number previous_state)** - Executa uma transição a partir do prompt/solicitação do usuário, no estado atual (que será o previous_state), para um novo estado criado. A transição é registrada. Geralmente, é executada **APÓS** o Agente de IA completar uma tarefa para um prompt dado do usuário

**arbitrary_state_transition(number current_state, number next_state)** - Executa uma transição arbitrária do estado atual para um número de estado dado. A transição é registrada

**get_current_state_number()** - Retorna apenas o número do estado gerenciado atual

**get_current_state_info()** - Retorna informações (tupla) do estado gerenciado atual. Fornece o contexto necessário para o Agente de IA e deve ser chamado **ANTES** de enviar qualquer prompt/solicitação para ele

**get_current_state_transitions()** - Retorna todas as transições (transition_id) para o estado gerenciado atual

**get_state_info(number state)** - Retorna todas as informações (tupla) para um número de estado dado

**get_state_transitions(number state)** - Retorna todas as transições (transition_id) para um número de estado dado

**get_transition_info(number transition_id)** - Retorna informações (tupla) de uma transição dada

**search_states(string text)** - Retorna todos os estados (número do estado) que têm o texto parâmetro contido em seu prompt (um contexto)

**track_transitions()** - Retorna informações (transition_id) das últimas 5 transições em sequência (se existir) do estado atual

**total_states()** - Retorna o número total de estados gerenciados pelo gerenciador de estado. Também ajuda a rastrear o último número usado para numeração de estados

## Regras

1. Definir um contador universal para a máquina de estado atual - total_states()
2. Dockerizar tudo
3. Criar cópia e realizar versionamento (usando git), se ainda não foi feito, do projeto atual (considerando .gitignore) para um volume do contêiner
4. Banco de dados de transição: id/índice, current_state, next_state, date_time
5. Um banco de dados de conhecimento gráfico (Neo4j) pode armazenar um estado como um nó e uma transição como uma relação
   5.1. Se um conhecimento gráfico não puder ser usado, um banco de dados SQLite pode realizar a tarefa. Não é perfeito, mas possível
6. Uma transição não pode ser duplicada

## Dependências

1. Docker + Git (pode ser baixado durante a criação do contêiner)
2. Neo4j - Para banco de dados de conhecimento gráfico

## Ideias Loucas

1. Armazenar a transição de estado em uma blockchain