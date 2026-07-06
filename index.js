import express from 'express';
import cors from 'cors';
import { validateTmaData } from '@velwix/tma-auth';

const app = express();
// Render muhitida port dinamik bo'ladi, mahalliy ishlatish uchun 3000
const PORT = process.env.PORT || 3000;

// Barcha so'rovlar (CORS) uchun ruxsat berish
app.use(cors({
  origin: '*',
  methods: ['POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// Kelayotgan JSON body formatini o'qish uchun middleware
app.use(express.json());

// Siz so'ragan /api/test endpointi (Faqat POST so'rovlari uchun)
app.post('/api/test', async (req, res) => {
  try {
    const { initData } = req.body;

    if (!initData) {
      return res.status(400).json({ 
        success: false, 
        error: "initData topilmadi" 
      });
    }

    // Render'dagi muhit o'zgaruvchisidan bot tokenini olamiz
    const botToken = process.env.TELEGRAM_BOT_TOKEN;

    if (!botToken) {
      return res.status(500).json({ 
        success: false, 
        error: "Serverda TELEGRAM_BOT_TOKEN sozlanmagan" 
      });
    }

    // Telegram ma'lumotlarini validatsiya qilish
    const result = await validateTmaData(initData, botToken, {
      expiresIn: 3600 // 1 soat vaqt cheklovi
    });

    // Muvaffaqiyatli javob
    return res.status(200).json({ 
      success: true, 
      user: result.user 
    });

  } catch (error) {
    // Validatsiyadan o'ta olmaganda yoki boshqa xatoliklarda
    return res.status(401).json({ 
      success: false, 
      error: error.message 
    });
  }
});

// Noto'g'ri manzillar uchun catch-all router
app.use((req, res) => {
  res.status(404).json({ success: false, error: "Sahifa topilmadi" });
});

// Serverni ishga tushirish (0.0.0.0 Render uchun majburiy)
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server ${PORT}-portda muvaffaqiyatli ishga tushdi`);
});
