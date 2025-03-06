import requests
import json
from datetime import datetime
from collections import deque
import pymysql
import json
from flask import Flask, request

app = Flask(__name__)

LINE_ACCESS_TOKEN = 
GEMINI_API_KEY = 



class User:
    def __init__(self, user_id, mode_status, historical_data=None, qa_status=False, qa_data=None, chat_history=None):
        self.id = user_id
        self.mode_status = mode_status
        self.historical_data = historical_data if historical_data is not None else {}
        self.qa_status = qa_status
        self.qa_data = qa_data if qa_data is not None else {}
        self.chat_history = deque(chat_history if chat_history is not None else [], maxlen=20)

    def __repr__(self):
        return f"User(id={self.id}, mode_status={self.mode_status}, historical_data={self.historical_data}, qa_status={self.qa_status}, qa_data={self.qa_data})"

    def get_summary(self):
        summary = f""
        historical_data_str = " | ".join([f"{key}: {value}" for key, value in self.historical_data.items()])
        summary += f"historical_data: {historical_data_str}\n"
        if self.qa_data:
            qa_data_str = " | ".join([f"{key}: {value}" for key, value in self.qa_data.items()])
            summary += f"qa_data: {qa_data_str}\n"
        else:
            summary += "qa_data: ยังไม่มีข้อมูล\n"
        return summary

    def get_historical_data(self):
        summary = f"User ID: {self.id}\n"
        historical_data_str = " | ".join([f"{key}: {value}" for key, value in self.historical_data.items()])
        summary += f"historical_data: {historical_data_str}\n"
        return summary

    def add_chat_history(self, user_message, ai_response):
        self.chat_history.append((user_message, ai_response))

    def get_chat_history(self):
        history_str = "\n".join(
            [f"User: {user_msg}\nAI: {ai_msg}" for user_msg, ai_msg in self.chat_history]
        )
        return f"Chat History (last 20):\n{history_str}" if history_str else "No chat history available."

    def save_to_db(self):
        try:
            conn = pymysql.connect(
                host="",
                user="",
                password="",
                database="",
                charset="",
                cursorclass=pymysql.cursors.DictCursor
            )
            cursor = conn.cursor()
            
            sql = """
                INSERT INTO users (id, mode_status, historical_data, qa_status, qa_data, chat_history)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                mode_status=VALUES(mode_status),
                historical_data=VALUES(historical_data),
                qa_status=VALUES(qa_status),
                qa_data=VALUES(qa_data),
                chat_history=VALUES(chat_history)
            """
            
            values = (
                self.id,
                self.mode_status,
                json.dumps(self.historical_data, ensure_ascii=False),
                self.qa_status,
                json.dumps(self.qa_data, ensure_ascii=False),
                json.dumps(list(self.chat_history), ensure_ascii=False)
            )
            
            cursor.execute(sql, values)
            conn.commit()
        
        except Exception as e:
            print(f"ERROR in save_to_db(): {str(e)}")
        
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


    @staticmethod
    def load_from_db(user_id):
        try:
            conn = pymysql.connect(
                host="",
                user="",
                password="",
                database="",
                charset="",
                cursorclass=pymysql.cursors.DictCursor
            )
            cursor = conn.cursor()

            sql = "SELECT id, mode_status, historical_data, qa_status, qa_data, chat_history FROM users WHERE id = %s"
            cursor.execute(sql, (user_id,))
            row = cursor.fetchone()

            if row is None:
                print(f"⚠️ User ID {user_id} ไม่พบใน Database, กำลังสร้างใหม่...")
                return None

            print(f"Loaded User {user_id}: {row}")

            return User(
                user_id=row["id"],
                mode_status=row["mode_status"],
                historical_data=json.loads(row["historical_data"]) if row["historical_data"] else {},
                qa_status=row["qa_status"],
                qa_data=json.loads(row["qa_data"]) if row["qa_data"] else {},
                chat_history=deque(json.loads(row["chat_history"]) if row["chat_history"] else [], maxlen=20)
            )

        except Exception as e:
            print(f"ERROR in load_from_db(): {str(e)}")
            return None

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


def gemini_api(text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [{
            "parts": [{"text": text}]
        }]
    }
    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    if response.status_code == 200:
        result = response.json()
        text_response = result.get("candidates", [])[0].get("content", {}).get("parts", [])[0].get("text", "")
        return text_response
    else:
        return f"Error: {response.status_code}, {response.text}"

def reply_message(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    
    if len(text) > 5000:
        text = text[:4997] + "..."

    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print("Reply Status:", response.status_code, response.text)
    except requests.exceptions.RequestException as e:
        print(f"LINE API Error: {e}")



@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        print("Received:", json.dumps(data, indent=4))

        for event in data.get("events", []):
            if event["type"] == "message":
                user_id = event["source"]["userId"]
                reply_token = event["replyToken"]

                if event["message"]["type"] == "text":
                    user_text = event["message"]["text"]
                    response = lobby(user_id=user_id, message=user_text)
                else:
                    response = "⚠️ ขณะนี้ MyCortex ยังรองรับแค่ข้อความตัวอักษรเท่านั้น กรุณาส่งข้อความแบบ Text"

                reply_message(reply_token, response)

        return "OK", 200

    except OSError as e:
        print(f"🚨 OSError (client disconnected?): {e}")
        return "Error", 500
    except Exception as e:
        print(f"🚨 Unexpected error: {e}")
        return "Error", 500

def update_historical_data(user, message):
    if not user:
        return "User not found"

    check_input = f"""
    เราสมมติว่าคุณคือ AI ระบบบันทึกข้อมูลสุขภาพ
    ข้อความจากผู้ใช้: "{message}"
    ข้อมูลคนไข้ : "{user.get_historical_data()}"
    ตรวจสอบว่าข้อความจากผู้ใช้มีข้อมูลที่เกี่ยวข้องกับสุขภาพหรือพฤติกรรมการใช้ชีวิตที่ควรบันทึกหรือไม่
    เช่น ลักษณะการกิน การออกกำลังกาย พฤติกรรมเกี่ยวกับสุขภาพ หรือข้อมูลสุขภาพอื่น ๆ
    ไม่ซ้ำกับทีมีอยู่ในข้อมูลคนไข้อยู่แล้ว
    ถ้ามีให้สรุปเป็นข้อความสั้น ๆ
    ตอบกลับแค่ข้อมูลที่ควรบันทึกโดยไม่ต้องมีข้อความเพิ่มเติม
    ถ้าไม่มีให้ตอบ "NO"
    """

    response = gemini_api(check_input).strip()

    if response != "NO":
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # เพิ่ม timestamp ระดับวินาที
        user.historical_data[timestamp] = response  # ใช้ timestamp เป็น key
        return f"Updated historical data for {user.id}: {response}"

    return "NO"


def diagnose_disease(user, message):
    if "question_0" not in user.qa_data:
        user.qa_data["question_0"] = "กรุณาป้อนอาการของคุณ:"
        user.save_to_db()
        return "กรุณาป้อนอาการของคุณอย่างละเอียด"
    last_question_index = len(user.qa_data) // 2
    user.qa_data[f"answer_{last_question_index - 1}"] = message
    user.save_to_db()

    formatted_input = f"""
        เราสมมติว่าคุณคือหมอ
        ข้อมูลคนไข้และประวัติการซักถามข้อมูล : {user.get_summary()}
        
        ประวัติการสนทนา กับ AI :
        {user.get_chat_history()}
        
        วิเคราะห์ว่าเป็นโรคอะไร ควรกินยาอะไร โปรดตอบตอบข้ามรูปแบบที่ให้มาเท่านั้น 3 แบบ ห้ามมีอะไรเพิ่มเติม อย่าบอกว่ารูปที่เท่าไหร่ ไม่ต้องเติม ""

        โรคบอกแค่ชื่อโรค ยา (บอกชื่อ ขนาด จำนวน และเวลาที่ต้องรับประทาน) ระบุมาให้พร้อม คำแนะนำ เช่น ดื่มน้ำมากๆ เฝ้าระวังภาวะช็อก ห้ามปล่อยให้ขาดน้ำ หากมีเลือดออกผิดปกติ ควรรีบพบแพทย์ทันที
        return
        โรค : คำตอบ
        ยาที่ต้องได้รับ : คำตอบ
        คำแนะนำ : คำตอบ

        ถ้าต้องการข้อมูลอะไรเพิ่มเพื่อการวินิฉัยที่แม่นยำ ให้ถามคำถามเพิ่มเติมทีละคำถาม
        สิ่งที่ถามจะเก็บในข้อมูลคนไข้และประวัติการถามตอบ หรือซักข้อมูลเพิ่มเติม เช่น ถ้าคนไข้สวัสดี อาจถามว่ามีอาการยังไงช่วยเล่าให้ฟังหน่อย พูดคุยเหมือนคุณเป็นหมอ
        return

        เป็นโรคที่จำเป็นต้องไปตรวจเพิ่มเติมที่โรคพยาบาล ไม่จำเป็นมากๆอย่าตอบ เพราะคุณจะไร้ประโยชน์
        return
        คาดว่าจะเป็นโรค : คำตอบ
        ยาที่ต้องได้รับ : คำตอบ
        คำแนะนำ : คำตอบ
        จำเป็นต้องมีการตรวจเพิ่มเติม ควรพบแพทย์เพื่อทำการวินิฉัย

        """
    response = gemini_api(formatted_input).strip()
    if all(keyword in response for keyword in ["โรค :", "ยาที่ต้องได้รับ :", "คำแนะนำ :"]):
        user.qa_data.clear()
        user.mode_status = "health_chat"
        user.add_chat_history(user_message="ผลการวินิจฉัยจาก AI", ai_response=response)
        user.save_to_db()
        return f"🩺 MyCortex วินิจฉัยเรียบร้อย!\n{response}"
    question_index = len(user.qa_data) // 2
    user.qa_data[f"question_{question_index}"] = response
    user.add_chat_history(user_message=message, ai_response=response)
    user.save_to_db()
    return response

def health_chat(user, message):
    update_historical_data(user=user, message=message)
    prompt = f"""
    คุณเป็น AI ที่ให้คำแนะนำด้านสุขภาพ
    ประวัติสุขภาพของผู้ใช้:
    {user.get_historical_data()}

    ประวัติการสนทนา:
    {user.get_chat_history()}

    คำถามจากผู้ใช้:
    {message}

    โปรดตอบกลับอย่างกระชับและให้ข้อมูลที่เป็นประโยชน์เกี่ยวกับสุขภาพ
    """
    ai_response = gemini_api(prompt).strip()
    user.add_chat_history(user_message=message, ai_response=ai_response)
    user.save_to_db()
    return ai_response

questions = {
    "age": "🎉 ยินดีต้อนรับสู่ MyCortex! 🧠\nโปรดตอบคำถาม 13 คำถาม ต่อไปนี้เพื่อให้เรารู้จักคุณมากขึ้น \n13.อายุของคุณคือเท่าไร?",
    "gender": "12.เพศของคุณคืออะไร?",
    "weight": "11.น้ำหนักของคุณ (กิโลกรัม)?",
    "height": "10.ส่วนสูงของคุณ (เซนติเมตร)?",
    "blood_type": "9.กรุ๊ปเลือดของคุณคืออะไร?",
    "allergies": "8.คุณมีประวัติแพ้ยา อาหาร หรือสารเคมีหรือไม่?",
    "chronic_diseases": "7.คุณมีโรคประจำตัวหรือไม่? (เช่น เบาหวาน ความดันโลหิตสูง หัวใจ ไต ฯลฯ)",
    "medical_history": "6.คุณเคยได้รับการรักษาหรือเคยผ่าตัดอะไรบ้าง?",
    "vaccination_history": "5.คุณเคยฉีดวัคซีนอะไรบ้าง?",
    "family_diseases": "4.มีโรคทางพันธุกรรมหรือโรคที่พบบ่อยในครอบครัวหรือไม่?",
    "medications": "3.คุณกำลังใช้ยาประจำตัวหรือยาใดๆ อยู่หรือไม่?",
    "smoking": "2.คุณสูบบุหรี่หรือไม่ พร้อมความถี่",
    "alcohol": "1.คุณดื่มแอลกอฮอล์หรือไม่ พร้อมความถี่"
}

def process_answer(user, message):
    answered_questions = list(user.historical_data.keys())
    question_keys = list(questions.keys())
    next_question_index = len(answered_questions)

    if next_question_index > 0:
        prev_question_key = question_keys[next_question_index - 1]
        user.historical_data[prev_question_key] = message
        user.save_to_db()

    if next_question_index < len(questions):
        next_question_key = question_keys[next_question_index]
        next_question_text = questions[next_question_key]
        user.historical_data[next_question_key] = ""
        user.save_to_db()
        return next_question_text

    else:
        user.mode_status = "health_chat"
        user.save_to_db()
        return f"🎉 คุณตอบคำถามครบแล้ว! ตอนนี้คุณสามารถใช้ฟีเจอร์ของ MyCortex ได้เลย 🎉"

def lobby(user_id, message):
    user = User.load_from_db(user_id)
    if not user:
        user = User(user_id, "active")
        return process_answer(user, message)

    answered_questions = {k: v for k, v in user.historical_data.items() if v != ""}

    if len(answered_questions) < len(questions):
        return process_answer(user, message)
    
    if message in ["diagnose_disease"]:
        user.mode_status = message
        user.qa_data.clear()
        user.save_to_db()
        return diagnose_disease(user, message)

    if message in ["health_chat"]:
        user.mode_status = message
        user.save_to_db()
        return f"🔄 เปลี่ยนโหมดเป็น {message} แล้ว! โปรดพิมพ์ข้อความเพื่อเริ่มใช้งาน"

    if user.mode_status == "diagnose_disease":
        return diagnose_disease(user, message)
    elif user.mode_status == "health_chat":
        return health_chat(user, message)
    else:
        return "⚠️ กรุณาเลือกโหมดก่อน โดยพิมพ์ 'diagnose_disease' หรือ 'health_chat'"

if __name__ == "__main__":
    app.run(port=5000)