# Visual Maps

Mermaid diagram source for the 3 README.md visual maps. Edit here, then copy
updated blocks into `README.md`.

See also: [[System-Overview]]

## Diagram A -- System Map

```mermaid
flowchart LR
    O[Operator] --> CLI[PolyTool CLI]

    CLI --> R1[Research Pipeline]
    CLI --> R2[RIS]
    CLI --> S1[SimTrader]
    CLI --> C1[Crypto Pair Bot]
    CLI --> D1[Data Import]
    CLI --> M1[Market Selection]
    CLI --> E1[Execution Layer]

    R1 --> KB[(kb/)]
    R1 --> ART[(artifacts/)]
    R2 --> KB
    S1 --> ART
    C1 --> ART
    D1 --> CH[(ClickHouse)]
    M1 --> ART
    E1 --> PM[Polymarket]

    CH --> G[Grafana]
    CLI --> ST[SimTrader Studio]
    CLI --> MCP[MCP Server]
    R2 --> N8N[n8n RIS Pilot]
```

## Diagram B -- First-Time Operator Path

```mermaid
flowchart TD
    A[Clone Repo] --> B[Create .venv]
    B --> C[Install Dependencies]
    C --> D[Copy .env.example to .env]
    D --> E[Set CLICKHOUSE_PASSWORD]
    E --> F[docker compose up -d]
    F --> G[Run python -m polytool --help]

    G --> H{What do you want to do first?}

    H --> I[Research Loop]
    H --> J[RAG]
    H --> K[SimTrader Shadow / Replay]
    H --> L[Crypto Pair Paper Run]

    I --> I1[wallet-scan]
    I1 --> I2[alpha-distill]
    I2 --> I3[hypothesis-register]

    J --> J1[rag-refresh]
    J1 --> J2[rag-query]

    K --> K1[simtrader quickrun]
    K --> K2[simtrader shadow]
    K --> K3[simtrader studio]

    L --> L1[crypto-pair-watch]
    L1 --> L2[crypto-pair-scan]
    L2 --> L3[crypto-pair-run]
```

## Diagram C -- Infrastructure and Operator Surfaces

```mermaid
flowchart LR
    subgraph LocalMachine[Local Machine]
        CLI[PolyTool CLI]
        ENV[.env]
        KB[(kb/)]
        ART[(artifacts/)]
    end

    subgraph DockerCompose[Docker Compose]
        CH[ClickHouse]
        GF[Grafana]
        API[API Service]
        RIS[RIS Scheduler]
        N8N[n8n optional]
        PBP[pair-bot-paper optional]
        PBL[pair-bot-live blocked]
    end

    CLI --> API
    CLI --> CH
    CLI --> KB
    CLI --> ART
    ENV --> API
    ENV --> CH
    CH --> GF
    RIS --> CH
    N8N --> RIS
    PBP --> CH
    PBL --> CH
```
