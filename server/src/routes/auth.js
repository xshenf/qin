const express = require('express');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const { User } = require('../db');
const router = express.Router();
const nodemailer = require('nodemailer');
const crypto = require('crypto');

// Secret key for JWT
const JWT_SECRET = process.env.JWT_SECRET || 'your_secret_key';

// Email Sender
const transporter = nodemailer.createTransport({
    host: process.env.SMTP_HOST,
    port: process.env.SMTP_PORT,
    secure: process.env.SMTP_SECURE === 'true', // true for 465, false for other ports
    auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASS,
    },
});

const sendVerificationEmail = async (email, token) => {
    const verificationLink = `http://localhost:3000/api/auth/verify-email?token=${token}`;

    try {
        const info = await transporter.sendMail({
            from: `"Guitar Practice App" <${process.env.SMTP_USER}>`,
            to: email,
            subject: "Verify your email",
            text: `Please verify your email by clicking the following link: ${verificationLink}`,
            html: `<p>Please verify your email by clicking the following link:</p><p><a href="${verificationLink}">${verificationLink}</a></p>`,
        });
        console.log("Message sent: %s", info.messageId);
    } catch (error) {
        console.error("Error sending email:", error);
        // We don't throw here to avoid failing the registration if email service is down
        // In a production app, you might want to handle this differently (e.g., retry queue)
    }
};

// CAPTCHA generation
const svgCaptcha = require('svg-captcha');

router.get('/captcha', (req, res) => {
    const captcha = svgCaptcha.create({
        size: 4,
        noise: 2,
        color: true,
        background: '#f0f0f0'
    });
    req.session.captcha = captcha.text.toLowerCase();
    res.type('svg');
    res.status(200).send(captcha.data);
});

// Register
router.post('/register', async (req, res) => {
    try {
        const { email, password, captcha } = req.body;

        // Check CAPTCHA
        if (!captcha || !req.session.captcha || captcha.toLowerCase() !== req.session.captcha) {
            return res.status(400).json({ message: '验证码错误或已过期。' });
        }
        // Clear captcha after use
        req.session.captcha = null;

        // Check if user exists
        const existingUser = await User.findOne({ where: { email } });
        if (existingUser) {
            return res.status(400).json({ message: 'Email already in use.' });
        }

        // Hash password
        const hashedPassword = await bcrypt.hash(password, 10);
        const verificationToken = crypto.randomBytes(32).toString('hex');

        // Create user
        const user = await User.create({
            email,
            password_hash: hashedPassword,
            verification_token: verificationToken,
            is_verified: true // Set to true for dev temporarily
        });

        // Send verification email
        // await sendVerificationEmail(email, verificationToken);

        res.status(201).json({ message: 'User registered. You can now login.' });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error during registration.' });
    }
});

// Login
router.post('/login', async (req, res) => {
    try {
        const { email, password } = req.body;

        const user = await User.findOne({ where: { email } });
        if (!user) {
            return res.status(400).json({ message: 'Invalid credentials.' });
        }

        // Check verification
        if (!user.is_verified) {
            return res.status(403).json({ message: 'Please verify your email first.' });
        }

        // Check password
        const isMatch = await bcrypt.compare(password, user.password_hash);
        if (!isMatch) {
            return res.status(400).json({ message: 'Invalid credentials.' });
        }

        // Generate token
        const token = jwt.sign(
            { id: user.id, email: user.email, role: user.role },
            JWT_SECRET,
            { expiresIn: '1h' }
        );

        res.json({ token, user: { id: user.id, email: user.email, role: user.role } });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error during login.' });
    }
});

// Verify Email
router.get('/verify-email', async (req, res) => {
    try {
        const { token } = req.query;
        const user = await User.findOne({ where: { verification_token: token } });

        if (!user) {
            return res.status(400).send('Invalid or expired verification token.');
        }

        user.is_verified = true;
        user.verification_token = null;
        await user.save();

        res.send('Email verified successfully! You can now login.');
    } catch (error) {
        console.error(error);
        res.status(500).send('Server error.');
    }
});

module.exports = router;
