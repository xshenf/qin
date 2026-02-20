console.log('Starting server...');
const express = require('express');
console.log('express loaded');
const cors = require('cors');
console.log('cors loaded');
let initDb, authRoutes, adminRoutes, historyRoutes;

try {
    ({ initDb } = require('./db'));
    console.log('db loaded');
    authRoutes = require('./routes/auth');
    console.log('authRoutes loaded');
    adminRoutes = require('./routes/admin');
    console.log('adminRoutes loaded');
    historyRoutes = require('./routes/history');
    console.log('historyRoutes loaded');
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
app.use('/api/user/history', historyRoutes);

// Serve Vue Frontend
const path = require('path');
const frontendPath = path.join(__dirname, '../../app/dist');
app.use(express.static(frontendPath));

// Fallback for Vue Router History Mode
app.get('*', (req, res) => {
    res.sendFile(path.join(frontendPath, 'index.html'));
});

// Initialize DB and start server
initDb().then(() => {
    app.listen(PORT, () => {
        console.log(`Server is running on http://localhost:${PORT}`);
    });
});
