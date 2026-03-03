# Modules

Python modules voor Server Up v2.

## Structuur per module

```
mijn-module/
├── __init__.py    # Flask Blueprint + ModuleBase subclass
└── module.json    # metadata
```

## module.json voorbeeld

```json
{
  "id": "mijn-module",
  "name": "Mijn Module",
  "description": "Wat doet deze module",
  "version": "1.0.0",
  "author": "bes-r",
  "tags": ["custom"]
}
```
