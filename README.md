# Greenlogy pre Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![GitHub release](https://img.shields.io/github/v/release/durcak/ha-greenlogy?include_prereleases&sort=semver)](https://github.com/durcak/ha-greenlogy/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.4%2B-03A9F4.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Neoficiálna integrácia pre zákazníkov slovenského dodávateľa elektriny [Greenlogy](https://www.greenlogy.com).
Zobrazí stav **virtuálnej batérie (Green VBattery)** a importuje **hodinové merania z elektromera distribútora**
zo zákazníckeho portálu [portal.greenlogy.com](https://portal.greenlogy.com) do Home Assistanta.

*English summary [below](#english).*

> [!WARNING]
> Greenlogy nemá verejné API. Integrácia používa rovnaké rozhranie ako ich webový portál, ktoré sa môže
> kedykoľvek zmeniť. Nejde o oficiálny produkt Greenlogy.

> [!NOTE]
> **Beta** – integrácia sa práve testuje. Ak niečo nefunguje, založte prosím
> [issue](https://github.com/durcak/ha-greenlogy/issues) aj s logom (bez hesla).

## Funkcie

- 🔋 **Stav virtuálnej batérie** a energia vyrobená / spotrebovaná od posledného ročného zúčtovania
- ⚡ **Hodinové merania odberu a dodávky** z elektromera distribútora v dlhodobých štatistikách HA –
  vrátane celej histórie od začiatku zmluvy
- 📊 Použiteľné na **Energy dashboarde** a v kartách *Štatistika* / *Graf štatistík*
- 💶 Ceny silovej elektriny (VT/NT) zo zmluvy
- 🔐 Nastavenie cez UI – stačí e-mail a heslo do zákazníckeho portálu

## Inštalácia

### HACS (odporúčané)

[![Otvoriť repozitár v HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=durcak&repository=ha-greenlogy&category=integration)

1. Kliknite na tlačidlo vyššie, alebo v HACS otvorte **⋮ → Vlastné repozitáre** a pridajte
   `https://github.com/durcak/ha-greenlogy` s kategóriou **Integrácia**.
2. Nainštalujte **Greenlogy**.
3. Reštartujte Home Assistant.

### Ručne

1. Stiahnite si [najnovšiu verziu](https://github.com/durcak/ha-greenlogy/releases).
2. Skopírujte priečinok `custom_components/greenlogy` do `config/custom_components/`.
3. Reštartujte Home Assistant.

## Nastavenie

[![Pridať integráciu](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=greenlogy)

**Nastavenia → Zariadenia a služby → Pridať integráciu → Greenlogy** a zadajte e-mail a heslo, ktorými sa
prihlasujete do zákazníckeho portálu Greenlogy. Integrácia si sama nájde virtuálnu batériu aj odberné a výrobné
miesto. Dáta sa obnovujú každé 3 hodiny. Ak heslo zmeníte, Home Assistant vás vyzve na zadanie nového.

## Entity

| Entita | Popis |
|---|---|
| Stav virtuálnej batérie | aktuálny zostatok vo virtuálnej batérii (kWh) |
| Vyrobené do VB od zúčtovania | energia pripísaná do batérie od posledného ročného zúčtovania |
| Spotrebované z VB od zúčtovania | energia odobratá z batérie od posledného ročného zúčtovania |
| Prenesené z minulého zúčtovania | zostatok, ktorý zostal z predchádzajúceho obdobia |
| Odber zo siete včera | podľa elektromera distribútora |
| Dodávka do siete včera | podľa elektromera distribútora |
| Merania k dispozícii do | do kedy sú hodinové merania naimportované (diagnostika) |
| Cena elektriny VT / NT | ceny silovej elektriny zo zmluvy (diagnostika) |

Čísla virtuálnej batérie sedia s portálom Greenlogy a platí:

```
stav = prenesené z minulého zúčtovania + vyrobené od zúčtovania − spotrebované od zúčtovania
```

Dátum začiatku obdobia je v atribúte `od` senzorov.

## Štatistiky a Energy dashboard

Integrácia importuje hodinové merania do dlhodobých štatistík:

| Štatistika | Popis |
|---|---|
| `greenlogy:grid_import` | odber zo siete |
| `greenlogy:grid_export` | dodávka do siete |

Pri prvom spustení sa stiahne celá dostupná história, potom sa dopĺňajú nové dni. Distribútor zverejňuje merania
s oneskorením zvyčajne 1–2 dni – štatistiky sú preto ideálne na **mesačné prehľady a porovnanie s faktúrou**.
Na sledovanie v reálnom čase je lepší vlastný merač (menič, Shelly, P1/RS485 a pod.).

Príklad karty s mesačným odberom a dodávkou:

```yaml
type: statistics-graph
title: Elektromer – mesačne
chart_type: bar
period: month
stat_types:
  - change
entities:
  - entity: greenlogy:grid_import
    name: Odber zo siete
  - entity: greenlogy:grid_export
    name: Dodávka do siete
```

Na Energy dashboarde ich vyberiete v **Nastavenia → Dashboardy → Energia → Elektrická sieť**.

## Riešenie problémov

Podrobný log zapnete v `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.greenlogy: debug
```

- **Nesprávny e-mail alebo heslo** – overte prihlásenie na [portal.greenlogy.com](https://portal.greenlogy.com).
- **Chýbajú merania za posledné dni** – distribútor ich ešte nezverejnil, doplnia sa automaticky.

## Prispievanie

Pull requesty a hlásenia chýb sú vítané. Integrácia vznikla pre vlastnú potrebu a otestovaná je na jednom
účte s virtuálnou batériou MAX a jedným odberným a výrobným miestom.

## Licencia

[MIT](LICENSE)

---

## English

Unofficial Home Assistant integration for customers of the Slovak electricity supplier
[Greenlogy](https://www.greenlogy.com). It reads the **virtual battery (Green VBattery)** balance and imports
**hourly smart-meter readings** (grid import/export) from the Greenlogy customer portal into long-term statistics,
usable on the Energy dashboard. Install via HACS as a custom repository, then add the integration and enter your
customer portal email and password. Greenlogy has no public API – this integration uses the same endpoints as the
web portal and may break if they change.
