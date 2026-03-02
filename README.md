# server-up 🐋

Persoonlijke docker stacks en modules voor Docker Manager v2.

## Structuur

```
server-up/
├── apps/                    # Docker Compose stacks (App Store)
│   ├── portainer/
│   │   ├── docker-compose.yml
│   │   ├── stack.json       # metadata (naam, beschrijving, tags)
│   │   └── README.md
│   └── ...
│
├── modules/                 # Python modules voor Docker Manager
│   └── ...
│
└── manager/                 # Docker Manager v2 zelf
    └── docker-compose.yml   # deploy instructies voor Docker Manager
```

## Gebruik

Docker Manager haalt automatisch de laatste versie op via git pull.
Stacks worden zichtbaar in de **App Store**.

## SSH Deploy Key

Voeg de publieke SSH-sleutel van je server toe als Deploy Key:
GitHub → Settings → Deploy Keys → Add deploy key (read-only)
