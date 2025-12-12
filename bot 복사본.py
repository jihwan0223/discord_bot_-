import discord
import os
import json
import certifi
import pytz
import random
import time
import ssl
import aiohttp
import asyncio
import tempfile
from discord.ext import commands
from discord import app_commands
from discord import Interaction, Member
from datetime import datetime
from datetime import date
from datetime import timedelta
from dotenv import load_dotenv


# tts
from gtts import gTTS
from discord.opus import load_opus, is_loaded


#Opus 라이브러리 수동 로드
opus_path = "/opt/homebrew/lib/libopus.dylib"


try:
    load_opus(opus_path)
    print("Opus loaded:", is_loaded())
except Exception as e:
    print("Opus load failed:", e)


# 전역변수
tts_enabled = False
tts_channel_id = None

POINT_FILE = "points.json"

# SSL 인증서 경로 지정
os.environ['SSL_CERT_FILE'] = certifi.where()
ssl_context = ssl.create_default_context(cafile=certifi.where())

# 토큰
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 봇 intents 설정
intents = discord.Intents.default()
intents.message_content = True


# 봇 생성
bot = commands.Bot(command_prefix="!", intents=intents)



# 봇 로그인
@bot.event
async def on_ready():
    # 세션 생성
    if not hasattr(bot, "aiohttp_session") or bot.aiohttp_session.closed:
        bot.aiohttp_session = aiohttp.ClientSession()

    print("clear")
#    for guild in bot.guilds:
#        print(f"- {guild.name} ({guild.id})")

    if not getattr(bot, "synced", False):
        try:
            synced = await bot.tree.sync()
            print(f"{len(synced)}")
        except Exception as e:
            print(f"명령어 등록 실패: {e}")

        bot.synced = True



# 관리자 전용 명령어
@bot.tree.command(name="admin", description="사용자에게 관리자 권한이 있는지 확인합니다.") 
@app_commands.checks.has_permissions(administrator=True)
async def admin(interaction: discord.Interaction):
    await interaction.response.send_message("이에", ephemeral=True)

@bot.tree.command(name="청소", description="최근 메시지 N개 삭제")
@app_commands.checks.has_permissions(manage_messages=True)
async def 청소(interaction: discord.Interaction, 갯수: int):
    await interaction.response.defer()
    try:
        deleted = await interaction.channel.purge(limit = 갯수 + 1)
        await interaction.followup.send(f"{len(deleted)-1}개의 메시지를 삭제했어요!.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("메시지를 삭제할 권한이 없어요!", ephemeral=True)

@bot.tree.command(name="이름변경", description="봇의 닉네임을 변경합니다")
@app_commands.checks.has_permissions(change_nickname=True)
async def 이름변경(interaction: discord.Interaction, 새이름: str):
    try:
        await interaction.user.guild.me.edit(nick=새이름)
        await interaction.response.send_message(f"닉네임이 '{새이름}'(으)로 변경되었어요!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("닉네임을 변경할 권한이 없어요!", ephemeral=True)

# 타임아웃
@bot.tree.command(name="타임아웃", description="사용자를 타임아웃 시킵니다")
@app_commands.checks.has_permissions(moderate_members=True)
async def 타임아웃(interaction: Interaction, 대상: Member, 분: int, 이유: str):
    await interaction.response.defer()

    until_time = discord.utils.utcnow() + timedelta(minutes=분)

    try:
        await 대상.timeout(until_time, reason=이유)
        await interaction.followup.send(f"{대상.mention}님이 {분}분 동안 타임아웃 되었어요! 이유: {이유}", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("타임아웃을 시킬 권한이 없어요!", ephemeral=True)


@bot.tree.command(name="타임아웃해제", description="사용자의 타임아웃을 해제합니다")
@app_commands.checks.has_permissions(moderate_members=True)
async def 타임아웃해제(interaction: discord.Interaction, 대상: discord.Member):
    try:
        await 대상.edit(timed_out_until=None)
        await interaction.response.send_message(f"{대상.mention}님의 타임아웃이 해제되었어요!", ephemeral=False)
    except Exception as e:
        await interaction.response.send_message("타임아웃 해제에 실패했어요!", ephemeral=True)


# tts
@bot.tree.command(name="join", description="tts 초대")
async def join(interaction: discord.Interaction):
    global tts_enabled, tts_channel_id

    if not interaction.user.voice or not interaction.user.voice.channel:
        return await interaction.response.send_message("음성 채널에 들어가 있어야 해요!")

    tts_enabled = True 
    tts_channel_id = interaction.channel.id


    # tts 시작
    voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    channel = interaction.user.voice.channel
    

    if voice and voice.is_connected():
        if voice.channel != channel:
            await voice.move_to(channel)  # 다른 채널이면 이동
    else:
        await channel.connect()  # 연결되어 있지 않으면 연결

    await interaction.response.send_message("이너쪼인!")


# tts 종료
@bot.tree.command(name="leave", description="tts 종료")
async def leave(interaction: discord.Interaction):
    global tts_enabled, tts_channel_id
    voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)

    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("이 명령어는 서버 관리자만 사용할 수 있습니다!")

    if not interaction.user.voice or not interaction.user.voice.channel:
        return await interaction.response.send_message("음성 채널에 들어가 있어야 해요!")

    tts_enabled = False
    tts_channel_id = None
    await voice.disconnect()
    await interaction.response.send_message("아웃쪼인!")


# tts 재생
@bot.event
async def on_message(message):
    global tts_enabled, tts_channel_id

    if message.author.bot or not tts_enabled or message.channel.id != tts_channel_id:
        return
    
    voice = discord.utils.get(bot.voice_clients, guild=message.guild)
    if not voice or not voice.is_connected():
        return
    
    tts_text = message.content
    if not tts_text.strip():
        return
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
        tts = gTTS(tts_text, lang="ko", tld="com")
        tts.save(f.name)
        tts_path = f.name

    # 재생
    source = discord.FFmpegPCMAudio(tts_path)
    voice.play(source)

    while voice.is_playing():
        await asyncio.sleep(0.1)
    os.remove(tts_path)

    await bot.process_commands(message)



# 기본
@bot.tree.command(name="봇", description="봇이 살아있는지 확인합니다")
async def 봇(interaction: discord.Interaction):
    await interaction.response.send_message("살음")

@bot.tree.command(name="ㅇㅇ", description="ㅇㅇ")
async def ㅇㅇ(interaction: discord.Interaction):
    await interaction.response.send_message("ㅇㅇ")

@bot.tree.command(name="ㄴㄴ", description="ㄴㄴ")
async def ㄴㄴ(interaction: discord.Interaction):
    await interaction.response.send_message("ㄴㄴ")

@bot.tree.command(name="인사", description="안녕")
async def 인사(interaction: discord.Interaction):
    await interaction.response.send_message("안녕")



# code
@bot.tree.command(name="python", description="'Hello, World!' 를 Python 코드로 출력합니다")
async def python(interaction: discord.Interaction):
    await interaction.response.send_message("```python\nprint(\"Hello, World!\")```")

@bot.tree.command(name="java", description="'Hello, World!' 를 Java 코드로 출력합니다")
async def java(interaction: discord.Interaction):
    await interaction.response.send_message("```java\npublic class Main {\n    public static void main(String[] args) {\n        System.out.println(\"Hello, World!\");\n    }\n}```")

@bot.tree.command(name="ruby", description="'Hello, World!' 를 Ruby 코드로 출력합니다")
async def ruby(interaction: discord.Interaction):
    await interaction.response.send_message("```ruby\nputs(\"Hello, World!\")```")

@bot.tree.command(name="swift", description="'Hello, World!' 를 Swift 코드로 출력합니다")
async def swift(interaction: discord.Interaction):
    await interaction.response.send_message("```swift\nprint(\"Hello, World!\")```")

@bot.tree.command(name="kotlin", description="'Hello, World!' 를 Kotlin 코드로 출력합니다")
async def kotlin(interaction: discord.Interaction):
    await interaction.response.send_message("```Kotlin\nfun main() {\n    println(\"Hello, World!\")\n}```")

@bot.tree.command(name="c", description="'Hello, World!' 를 C 코드로 출력합니다")
async def c(interaction: discord.Interaction):
    await interaction.response.send_message("```c\n#include <stdio.h>\n\nint main() {\n    printf(\"Hello, World!\");\n    return 0;\n}```")

@bot.tree.command(name="cpp", description="'Hello, World!' 를 C++ 코드로 출력합니다")
async def cpp(interaction: discord.Interaction):
    await interaction.response.send_message("```cpp\n#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << \"Hello, World!\" << endl;\n    return 0;\n}```")

@bot.tree.command(name="cshap", description="'Hello, World!' 를 C# 코드로 출력합니다")
async def cshap(interaction: discord.Interaction):
    await interaction.response.send_message("```csharp\nusing System;\nclass Program {\n    static void Main() {\n        Console.WriteLine(\"Hello, World!\");\n    }\n}```")

@bot.tree.command(name="엄랭", description="'Hello, World!' 를 엄랭 코드로 출력합니다")
async def 엄랭(interaction: discord.Interaction):
    await interaction.response.send_message("```umm\n어떻게\n엄.......... ..........\n식어,,,,,,,,,,,,,,,,,,,,,,,,,,,,ㅋ\n식어.ㅋ\n식어........ㅋ\n식어........ㅋ\n식어...........ㅋ\n식어,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,ㅋ\n식어,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,ㅋ\n식어,,,,,,,,,,,,,ㅋ\n식어...........ㅋ\n식어..............ㅋ\n식어........ㅋ\n식어ㅋ\n식어,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,ㅋ\n이 사람이름이냐ㅋㅋ```")

@bot.tree.command(name="아희", description="Hellom World! 를 아희 코드로 출력합니다")
async def 아희(interaction: discord.Interaction):
    await interaction.response.send_message("```ahi\n밤밣따빠밣밟따뿌\n빠맣파빨받밤뚜뭏\n돋밬탕빠맣붏두붇\n볻뫃박발뚷투뭏붖\n뫃도뫃희멓뭏뭏붘\n뫃봌토범더벌뿌뚜\n뽑뽀멓멓더벓뻐뚠\n뽀덩벐멓뻐덕더벅\n```")



# ??
    
@bot.tree.command(name="핑", description="핑!")
async def 핑핑(interaction: discord.Interaction):
    await interaction.response.send_message(f"봇의 핑: {round(bot.latency * 1000)}ms")


# 사진
@bot.tree.command(name="조롱이", description="조롱이 사진")
async def 조롱이(interaction: discord.Interaction):
    await interaction.response.send_message("https://i.namu.wiki/i/4mIMDgcMlALmD8F_3jcsvkBRHAYrdf5r2QfbO7tP0XyHf8l9FsUYTuzS3YzrBNxuClq4tQiySdknBngOjZqd_Q.webp")



# 랜덤 시간
@bot.tree.command(name="시간", description="랜덤 국가의 시간을 표시합니다")
async def 시간(interaction: discord.Interaction):
    TIMEZONE_NAMES = {
        "Asia/Seoul": "대한민국",
        "Asia/Tokyo": "일본",
        "Asia/Shanghai": "중국",
        "Asia/Kolkata": "인도",
        "Asia/Dubai": "아랍에미리트",
        "Asia/Bangkok": "태국",
        "Asia/Singapore": "싱가포르",
        "Asia/Hong_Kong": "홍콩",
        "Asia/Taipei": "대만",
        "Asia/Manila": "필리핀",
        "Asia/Kuala_Lumpur": "말레이시아",
        "Asia/Jakarta": "인도네시아",
        "Europe/London": "영국",
        "Europe/Paris": "프랑스",
        "Europe/Berlin": "독일",
        "Europe/Moscow": "러시아",
        "Europe/Madrid": "스페인",
        "Europe/Rome": "이탈리아",
        "Europe/Amsterdam": "네덜란드",
        "Europe/Zurich": "스위스",
        "Europe/Istanbul": "터키",
        "Europe/Stockholm": "스웨덴",
        "Europe/Warsaw": "폴란드",
        "America/New_York": "미국 (뉴욕)",
        "America/Los_Angeles": "미국 (로스앤젤레스)",
        "America/Chicago": "미국 (시카고)",
        "America/Toronto": "캐나다",
        "America/Mexico_City": "멕시코",
        "America/Sao_Paulo": "브라질",
        "America/Buenos_Aires": "아르헨티나",
        "America/Lima": "페루",
        "Africa/Cairo": "이집트",
        "Africa/Johannesburg": "남아프리카공화국",
        "Africa/Lagos": "나이지리아",
        "Africa/Nairobi": "케냐",
        "Africa/Casablanca": "모로코",
        "Australia/Sydney": "호주 (시드니)",
        "Australia/Perth": "호주 (퍼스)",
        "Australia/Melbourne": "호주 (멜버른)",
        "Pacific/Auckland": "뉴질랜드",
        "Pacific/Fiji": "피지",
    }
    tz = random.choice(list(TIMEZONE_NAMES.keys()))
    now = datetime.now(pytz.timezone(tz))
    country = TIMEZONE_NAMES[tz]
    await interaction.response.send_message(f"{country} ({tz}) 현재 시각: {now.strftime('%Y-%m-%d %H:%M:%S')}")


# 랜덤 고양이 짤
@bot.tree.command(name="고양이", description="랜덤 고양이 사진을 보여줍니다")
async def 고양이(interaction: discord.Interaction):
    await interaction.response.defer()

    session = getattr(bot, "aiohttp_session", None)
    if session is None or session.closed:
        bot.aiohttp_session = aiohttp.ClientSession()
        session = bot.aiohttp_session

    try:
        async with session.get("https://api.thecatapi.com/v1/images/search", timeout = 10) as resp:
            if resp.status != 200:
                return await interaction.followup.send("고양이 사진을 가져오지 못했어요!", ephemeral=False)

            data =  await resp.json()
            url = data[0].get("url")
            
        if not url:
            return await interaction.followup.send("고양이 사진 url을 가져오지 못했어요!", ephemeral=False)

        embed = discord.Embed(color=0xFFA500)
        embed.set_image(url = url)

        return await interaction.followup.send(embed = embed)

    except Exception as e:
        return await interaction.followup.send("고양이 사진을 가져오지 못했어요!", ephemeral=False)
            

# 랜덤 강아지 짤
@bot.tree.command(name="강아지", description="랜덤 강아지 사진을 보여줍니다")
async def 강아지(interaction: discord.Interaction):
    await interaction.response.defer()

    session = getattr(bot, "aiohttp_session", None)
    if session is None or session.closed:
        bot.aiohttp_session = aiohttp.ClientSession()
        session = bot.aiohttp_session

    try:
        async with session.get("https://dog.ceo/api/breeds/image/random", timeout = 10) as resp:
            if resp.status != 200:
                return await interaction.followup.send("강아지 사진을 가져오지 못했어요!", ephemeral=False)

            data =  await resp.json()
            url = data.get("message")
            
        if not url:
            return await interaction.followup.send("강아지 사진 url을 가져오지 못했어요!", ephemeral=False)

        embed = discord.Embed(color=0xFFA500)
        embed.set_image(url = url)

        return await interaction.followup.send(embed = embed)

    except Exception as e:
        return await interaction.followup.send("강아지 사진을 가져오지 못했어요!", ephemeral=False)
    



# 급식 정보
NEIS_API_KEY = "APIKEY"
ATPT = "R10"
SCHOOL = "8750829"


@bot.tree.command(name="급식", description="오늘의 급식 정보를 보여줍니다.")
@app_commands.describe(type="급식 시간을 선택하세요.")
@app_commands.choices(type=[
    app_commands.Choice(name="아침", value="조식"),
    app_commands.Choice(name="점심", value="중식"),
    app_commands.Choice(name="저녁", value="석식")
])

async def meal(interaction: discord.Interaction, type: app_commands.Choice[str]):
    await interaction.response.defer()

    today = datetime.now().strftime("%Y%m%d")

    url =(
        f"https://open.neis.go.kr/hub/mealServiceDietInfo?Type=json"
        f"&KEY={NEIS_API_KEY}&ATPT_OFCDC_SC_CODE={ATPT}"
        f"&SD_SCHUL_CODE={SCHOOL}&MLSV_YMD={today}"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

        if "mealServiceDietInfo" not in data:
            return await interaction.followup.send("오늘 급식 정보가 없습니다.")

        rows = data["mealServiceDietInfo"][1]["row"]

        meal_row = None
        for row in rows:
            if row["MMEAL_SC_NM"] == type.value:
                meal_row = row
                break

        if not meal_row:
            return await interaction.followup.send(f"오늘 {type.name} 급식이 없습니다.")

        meal_text = meal_row["DDISH_NM"].replace("<br/>", "\n")

        embed = discord.Embed(
            title = f"오늘의 {type.name} 급식",
            description = meal_text,
            color = 0x00AAFF
        )
        await interaction.followup.send(embed = embed)

    except Exception as e:
        await interaction.followup.send("급식 정보를 가져오는 중 오류가 발생했습니다.")


#도박 기능
# json
def load_data():
    if not os.path.exists("users.json"):
        with open("users.json", "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4)
    with open("users.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# 유저 정보 초기화 
def ensure_user(user_id: int, username: str):
    data = load_data()
    uid = str(user_id)

    if uid not in data:
        data[uid] = {
            "name": username,
            "money": 0,
            "last_daily": "0"
        }
        save_data(data)
        return data

    # name 없으면 추가
    if "name" not in data[uid]:
        data[uid]["name"] = username

    # 닉네임 변경 시 업데이트
    if data[uid]["name"] != username:
        data[uid]["name"] = username

    save_data(data)
    return data


# 돈 확인 
@bot.tree.command(name="돈", description="현재 보유 금액을 확인합니다.")
async def money(interaction: discord.Interaction):

    user_id = interaction.user.id
    username = interaction.user.display_name

    data = ensure_user(user_id, username)
    money = data[str(user_id)]["money"]

    await interaction.response.send_message(f"💰 {username} 님의 보유 금액: **{money}원**")



# 랭킹
@bot.tree.command(name="랭킹", description="돈 랭킹을 확인합니다.")
async def ranking(interaction: discord.Interaction):

    data = load_data()
    ranking = sorted(data.items(), key=lambda x: x[1]["money"], reverse=True)

    embed = discord.Embed(title="💰 돈 랭킹 TOP 10", color=0xFFD700)

    for i, (user_id, info) in enumerate(ranking[:10], start=1):

        member = interaction.guild.get_member(int(user_id))
        name = member.display_name if member else info["name"]

        embed.add_field(name=f"#{i} {name}", value=f"💵 {info['money']}원", inline=False)

    await interaction.response.send_message(embed=embed)

    embed = discord.Embed(title="💰 돈 랭킹 TOP 10", color=0xFFD700)


# 출석 체크
@bot.tree.command(name="돈받기", description="일일 출석 체크로 10000원을 받습니다.")
async def daily_money(interaction: discord.Interaction):

    user_id = interaction.user.id
    username = interaction.user.display_name

    data = ensure_user(user_id, username)

    today = str(date.today())
    last = data[str(user_id)]["last_daily"]

    if last == today:
        return await interaction.response.send_message("❌ 오늘 이미 돈받기를 했습니다!", ephemeral=True)

    data[str(user_id)]["money"] += 10000
    data[str(user_id)]["last_daily"] = today
    save_data(data)

    await interaction.response.send_message(
        f"💰 10000원이 지급되었습니다!\n"
        f"현재 금액: **{data[str(user_id)]['money']}원**")
    

# 노동
@bot.tree.command(name="돈벌기", description="노동을 하여 돈을 법니다.")
async def daily_money(interaction: discord.Interaction):

    user_id = interaction.user.id
    username = interaction.user.display_name

    data = ensure_user(user_id, username)
    user_id = str(user_id)

    if "last_work" not in data[user_id]:
        data[user_id]["last_work"] = 0

    # 쿨타임
    now = time.time()
    cooldown = 30 

    if now - data[user_id]["last_work"] < cooldown:
        remain = int(cooldown - (now - data[user_id]["last_work"]))
        return await interaction.response.send_message(
            "⏳ 휴식시간 입니다! {remain}초 후 다시 시도하세요.", ephemeral=True)

    data = ensure_user(user_id, username)

    data[user_id]["last_work"] = now
    data[str(user_id)]["money"] += 100
    save_data(data)

    await interaction.response.send_message(
        f"💰 최저시급 100원이 지급되었습니다!\n"
        f"현재 금액: **{data[str(user_id)]['money']}원**")



# 도박 명령어
@bot.tree.command(name="도박", description="합법임")
@app_commands.describe(choice="1 또는 2를 선택하세요.", bet="배팅 금액을 입력하세요.")
async def gamble(interaction: discord.Interaction, choice: int, bet: app_commands.Range[int, 500, None]):

    if choice not in [1, 2]:
        return await interaction.response.send_message("❌ 1 또는 2만 입력할 수 있어요!", ephemeral=True)

    await interaction.response.defer()

    user_id = interaction.user.id
    username = interaction.user.display_name

    data = ensure_user(user_id, username)
    money = data[str(user_id)]["money"]

    if money < bet:
        return await interaction.followup.send(f"❌ 보유 금액 부족!\n현재 금액: {money}원", ephemeral=True)

    bot_choice = random.choice([1, 2])

    # 확률
    win = random.choice([True, False])

    if win and bot_choice == choice:
        data[str(user_id)]["money"] += bet
        result = f"🎉 성공! +{bet}원"
    else:
        data[str(user_id)]["money"] -= bet
        result = f"💀 실패... -{bet}원"

    save_data(data)

    await interaction.followup.send(
        f"🎰 **도박 결과**\n"
        f"확률 : 50%\n\n"
        f"{result}\n\n"
        f"💰 현재 금액: {data[str(user_id)]['money']}원"
    )

# 초기화
@bot.tree.command(name="초기화", description="???")
async def 초기화(interaction: discord.Interaction):

    user_id = interaction.user.id
    username = interaction.user.display_name

    data = load_data()
    uid = str(user_id)

    if uid in data:
        del data[uid]
        save_data(data)
        await interaction.response.send_message("모든 기록을 초기화했습니다!")
        
    else:
        await interaction.response.send_message("돈없어", empheral=True)



# 오류 처리
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error


#bot.run("TOKEN")