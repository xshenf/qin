console.log('Starting server...');
const express = require('express');
console.log('express loaded');
const cors = require('cors');
console.log('cors loaded');
try {
    const { initDb } = require('./db');
    console.log('db loaded');
    const authRoutes = require('./routes/auth');
    console.log('authRoutes loaded');
    const adminRoutes = require('./routes/admin');
    console.log('adminRoutes loaded');
    require('dotenv').config();
    console.log('dotenv loaded');
} catch (e) {
    console.error('Error loading modules:', e);
    process.exit(1);
}

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/admin', adminRoutes);

app.get('/', (req, res) => {
    res.send('Guitar Practice App Backend is running.');
});

// Initialize DB and start server
initDb().then(() => {
    app.listen(PORT, () => {
        console.log(`Server is running on http://localhost:${PORT}`);
    });
});
