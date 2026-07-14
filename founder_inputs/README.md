# Founder mission inputs

This directory contains credential-free, founder-authored mission specifications.
Copy the example, edit only mission content, and keep API keys outside these files.
The example topic is sample data and is not AuraAI's selected flagship niche.
Source notes and source references are kept separate; both remain review-required
and neither is treated as independently verified evidence.

Validate without executing:

```shell
python -m company_missions.first_real_content.cli --input founder_inputs/first_content_mission.example.json --dry-run
```

Execute the deterministic mission and export its review package explicitly:

```shell
python -m company_missions.first_real_content.cli --input founder_inputs/first_content_mission.example.json --output-root outputs/missions --execute
```

Live mode requires both approval flags and uses a hidden interactive key prompt.
It never accepts credentials in the JSON file or command-line arguments. Every
mission stops at founder content review; rendering and publishing remain separate.
