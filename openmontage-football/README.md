# Boy Playing Football — OpenMontage Video

Renders a 45-second animated football video using OpenMontage + Remotion. No API keys needed.

## Steps

```bash
# 1. Clone OpenMontage
git clone https://github.com/calesthio/OpenMontage
cd OpenMontage

# 2. Install dependencies
make setup

# 3. Copy the render script and props from this folder into OpenMontage
cp /path/to/this/folder/boy-football.json remotion-composer/public/demo-props/
cp /path/to/this/folder/render.sh .

# 4. Run
bash render.sh
```

The video will be saved to:
```
projects/boy-football/renders/boy-football.mp4
```

Open it on Mac with:
```bash
open projects/boy-football/renders/boy-football.mp4
```
