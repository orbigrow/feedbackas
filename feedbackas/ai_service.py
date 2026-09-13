import requests
import json
from django.conf import settings
from decimal import Decimal
from feedbackas.models import AIUsageLog

def parse_name_gender_vocative(full_name='', first_name='', last_name=''):
    """
    Išskiria vardą, pavardę, nustato gramatinę lytį (male/female) ir suformuoja
    lietuvišką šauksmininko linksnį (vocative case) kreipimuisi.
    """
    first_name = (first_name or '').strip()
    last_name = (last_name or '').strip()

    if not first_name and full_name:
        clean = full_name.strip()
        # Jei pateiktas el. paštas (pvz. elena.zukauskas@...)
        if '@' in clean:
            clean = clean.split('@')[0].replace('_', '.').replace('-', '.')
        parts = clean.split()
        if len(parts) == 1 and '.' in parts[0]:
            parts = parts[0].split('.')
        first_name = parts[0].capitalize() if parts else ''
        if not last_name and len(parts) > 1:
            last_name = parts[-1].capitalize()

    first_name = first_name.strip().capitalize()
    last_name = last_name.strip().capitalize()
    
    fn_lower = first_name.lower()
    ln_lower = last_name.lower()
    
    # 1. Lyties nustatymas pagal lietuviškų vardų ir pavardžių galūnes
    gender = 'male' # numatytoji reikšmė
    
    female_last_suffixes = ('aitė', 'ytė', 'utė', 'ūtė', 'ienė', 'aite', 'yte', 'ute', 'iene', 'skė', 'ske', 'yté')
    male_last_suffixes = ('as', 'is', 'ys', 'us')
    
    if any(ln_lower.endswith(s) for s in female_last_suffixes):
        gender = 'female'
    elif any(ln_lower.endswith(s) for s in male_last_suffixes):
        gender = 'male'
    elif fn_lower.endswith(('a', 'ė', 'e')) and fn_lower not in ('nikita', 'kostas', 'jogaila', 'domas', 'adamas'):
        gender = 'female'
    elif fn_lower.endswith(('as', 'is', 'ys', 'us')):
        gender = 'male'
        
    # 2. Lietuviško vardo šauksmininkas (vocative)
    vocative = first_name
    if fn_lower.endswith('as'):
        vocative = first_name[:-2] + 'ai'
    elif fn_lower.endswith('ius'):
        vocative = first_name[:-3] + 'iau'
    elif fn_lower.endswith('is'):
        vocative = first_name[:-2] + 'i'
    elif fn_lower.endswith('ys'):
        vocative = first_name[:-2] + 'y'
    elif fn_lower.endswith('us'):
        vocative = first_name[:-2] + 'au'
    elif fn_lower.endswith('ė'):
        vocative = first_name[:-1] + 'e'
    elif fn_lower.endswith('a'):
        vocative = first_name
        
    return first_name, last_name, vocative, gender


class OpenRouterService:
    @staticmethod
    def _call_openrouter(prompt, user=None, company=None, request_type='general'):
        """
        Siunčia užklausą į OpenRouter API ir grąžina atsakymą bei rinka išlaidas.
        """
        api_key = settings.OPENROUTER_API_KEY
        model = getattr(settings, 'OPENROUTER_MODEL', 'google/gemma-3-27b-it:free')

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

        payload = {
            'model': model,
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.7,
            'max_tokens': 1024,
        }

        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()

        data = response.json()
        
        # Sukuriame loginį įrašą
        if user or company:
            usage = data.get('usage', {})
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            # OpenRouter dažniausiai grąžina 'cost', bet kai kurie modeliai/atsakymai gali turėti 'total_cost'
            total_cost = usage.get('cost') or usage.get('total_cost', 0.0)
            
            AIUsageLog.objects.create(
                user=user,
                company=company,
                request_type=request_type,
                model_name=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_cost=Decimal(str(total_cost)),
                raw_response=data
            )
            
        return data['choices'][0]['message']['content']

    @staticmethod
    def generate(ratings, keywords, comments, existing_feedback, colleague_name, user=None, company=None, language='lt', colleague_first_name=None, colleague_last_name=None):
        """
        Generuoja grįžtamąjį ryšį naudojant OpenRouter API.
        Atsižvelgia į kolegos lytį, naudoja taisyklingą šauksmininko kreipinį (be pavardės),
        kuria glaustą 2 pastraipų atsiliepimą ir užtikrina, kad sakinys nebūtų nukirstas.
        """
        first_name, last_name, vocative, gender = parse_name_gender_vocative(
            full_name=colleague_name,
            first_name=colleague_first_name,
            last_name=colleague_last_name
        )

        safe_comments = comments or ''
        safe_existing_feedback = existing_feedback or ''

        if language == 'lt':
            gender_desc = (
                'moteris (BŪTINAI naudok moteriškąją giminę: buvai aktyvi, iniciatyvi, patikima komandos narė, esi vertinama, parodei save kaip profesionalią)'
                if gender == 'female'
                else 'vyras (BŪTINAI naudok vyriškąją giminę: buvai aktyvus, iniciatyvus, patikimas komandos narys, esi vertinamas, parodei save kaip profesionalų)'
            )

            prompt = f"""
Veik kaip konkretus, kolegiškas komandos narys, būk empatiškas ir teik konstruktyvią kritiką.
Eik iš karto prie esmės, nereikia jokių formalių įžangų (pvz., GRIEŽTAI NERAŠYK „Norėjau pasidalinti atsiliepimu...“ ar „Štai mano pastebėjimai...“).

Adresatas:
- Vardas kreipiniui (šauksmininkas): {vocative}
- Lytis: {gender_desc}

GRIEŽTI REIKALAVIMAI:
1. KREIPINYS:
   - Atsiliepimą pradėk TIKSLIAI tokiu kreipiniu: {vocative},
   - NIEKADA nenaudok pavardės kreipimesi (griežtai draudžiama rašyti „{first_name} {last_name},“).

2. LYTIS IR GRAMATIKA:
   - GRIEŽTAI naudok taisyklingą giminę pagal nurodytą adresato lytį ({gender_desc})!

3. ILGIS IR STRUKTŪRA (SUTRAUKTAS IR GLAUSTAS):
   - Atsiliepimas turi būti GLAUSTAS, KONKRETUS, be vandens – apie 60–90 žodžių (maksimaliai 100 žodžių).
   - Tekstą sudaro TIK 2 trumpos pastraipos:
     * 1 pastraipa: kas labiausiai džiugina ir kur kolega labiausiai pasižymi (stiprybės, aukšti balai, geri komentarai).
     * 2 pastraipa: viena aiški tobulintina sritis su konkrečiu, kolegišku patarimu, kaip pasiekti geresnį rezultatą.
   - PABAIGA: BŪTINAI užbaik tekstą pilnu sakiniu. Niekada nenutrauk minties ar sakinio viduryje.

4. JOKIO MARKDOWN FORMATAVIMO:
   - Griežtai nenaudok jokių žvaigždučių (**), paryškinimų, antraščių ar sąrašo punktų. Tik paprastas tekstas, atskirtas pastraipomis.

Vertinimo duomenys (skalė 1-4: 1=Mokosi, 2=Daro, 3=Varo, 4=Pavyzdys):
- Komandinis darbas: {ratings.get('teamwork')}
- Komunikacija: {ratings.get('communication')}
- Iniciatyvumas: {ratings.get('initiative')}
- Techninės žinios: {ratings.get('technical_skills')}
- Problemų sprendimas: {ratings.get('problem_solving')}
- Raktiniai žodžiai: {keywords}
- Komentarai: {safe_comments}
- Ankstesnis kontekstas: {safe_existing_feedback}
"""
        else:
            prompt = f"""
Act as a constructive, empathetic team member providing feedback to a colleague.
Get straight to the point without boilerplate greetings (do NOT write "I wanted to share feedback...").

Recipient:
- Name for greeting: {first_name or vocative}

STRICT REQUIREMENTS:
1. GREETING:
   - Start directly with: {first_name or vocative},
   - NEVER use the colleague's last name in the greeting.

2. LENGTH AND STRUCTURE (CONCISE):
   - Keep it CONCISE, FOCUSED, and action-oriented: ~60–90 words (maximum 100 words).
   - Only 2 short paragraphs:
     * Paragraph 1: Strengths and where the colleague excels (high ratings and comments).
     * Paragraph 2: One key area for growth with practical, constructive advice.
   - ALWAYS finish with a complete, well-formed sentence. Never cut off mid-sentence.

3. NO MARKDOWN:
   - No asterisks, bold text, headers, or bullet points. Just clean paragraphs.

Evaluation data (scale 1-4: 1=Learning, 2=Doing, 3=Excelling, 4=Role Model):
- Teamwork: {ratings.get('teamwork')}
- Communication: {ratings.get('communication')}
- Initiative: {ratings.get('initiative')}
- Technical skills: {ratings.get('technical_skills')}
- Problem solving: {ratings.get('problem_solving')}
- Keywords: {keywords}
- Comments: {safe_comments}
- Additional context: {safe_existing_feedback}
"""

        response_text = OpenRouterService._call_openrouter(
            prompt, user=user, company=company, request_type='feedback_generation'
        )

        if not response_text:
            return response_text

        response_text = response_text.strip()

        # 1. Užtikriname švarų kreipinį (be pavardės)
        lines = response_text.split('\n')
        if lines:
            first_line = lines[0].strip()
            # Jei pirmoje eilutėje yra pavardė arba trūksta taisyklingo kreipinio
            if last_name and last_name.lower() in first_line.lower():
                lines[0] = f"{vocative},"
                response_text = '\n'.join(lines)
            elif not first_line.startswith(vocative):
                if first_line.endswith(','):
                    lines[0] = f"{vocative},"
                    response_text = '\n'.join(lines)
                else:
                    response_text = f"{vocative},\n\n" + response_text

        # 2. Užtikriname, kad sakinys pabaigoje nebūtų nukirstas viduryje
        response_text = response_text.strip()
        if not response_text.endswith(('.', '!', '?')):
            last_punct = max(response_text.rfind('.'), response_text.rfind('!'), response_text.rfind('?'))
            if last_punct > len(response_text) * 0.65:
                response_text = response_text[:last_punct + 1].strip()
            else:
                response_text += '.'

        return response_text

    @staticmethod
    def extract_strengths_weaknesses(feedback_text, comments_text, user=None, company=None):
        """
        Iš tekstinio atsiliepimo išveda stiprybes ir tobulintinas sritis JSON formatu.
        """
        if not feedback_text and not comments_text:
            return {"strengths": [], "improvements": []}

        prompt = f"""
        Išanalizuok žemiau pateiktą darbuotojo atsiliepimą ir išskirk dvi kategorijas:
        1. Stiprybės (gerosios savybės, ką darbuotojas daro gerai)
        2. Tobulintinos sritys (kas buvo paminėta kaip silpnybė arba kur galima tobulėti)

        Atsakymą pateik GRIEŽTAI TIK JSON formatu be jokio papildomo teksto, Markdown blokų ar paaiškinimų.
        Kiekvienas punktas turi būti suformuluotas trumpai (1-2 sakiniai).
        
        Pavyzdys:
        {{
            "strengths": ["Puikiai sprendžia technines problemas.", "Greitai mokosi naujų technologijų."],
            "improvements": ["Galėtų dažniau imtis iniciatyvos komandos susirinkimuose.", "Vertėtų tobulinti viešo kalbėjimo įgūdžius."]
        }}

        Atsiliepimas:
        {feedback_text}
        
        Papildomas komentaras:
        {comments_text}
        """

        try:
            response_text = OpenRouterService._call_openrouter(
                prompt, user=user, company=company, request_type='feedback_analysis'
            )
        except Exception as e:
            print(f"Failed to extract traits: {e}")
            return {"strengths": [], "improvements": []}

        try:
            cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
            data = json.loads(cleaned_text)
            return {
                "strengths": data.get("strengths", []),
                "improvements": data.get("improvements", [])
            }
        except Exception as e:
            print(f"Failed to parse extracted traits: {e}")
            return {"strengths": [], "improvements": []}
