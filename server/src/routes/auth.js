const express = require('express');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const { User } = require('../db');
const router = express.Router();
const nodemailer = require('nodemailer');
const crypto = require('crypto');

// Secret key for JWT
const JWT_SECRET = process.env.JWT_SECRET || 'your_secret_key';

// Mock Email Sender (Logs to console)
const sendVerificationEmail = async (email, token) => {
    const verificationLink = `http://localhost:3000/api/auth/verify-email?token=${token}`;
    console.log('---------------------------------------------------');
    console.log(`[EMAIL MOCK] To: ${email}`);
    console.log(`[EMAIL MOCK] Subject: Verify your email`);
    console.log(`[EMAIL MOCK] Link: ${verificationLink}`);
    console.log('---------------------------------------------------');

    // In production, use nodemailer with real credentials
    /*
    const transporter = nodemailer.createTransport({ ... });
    await transporter.sendMail({ ... });
    */
};

// Register
router.post('/register', async (req, res) => {
    try {
        const { email, password } = req.body;

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
            is_verified: false // Set to true for dev if needed, but false is safer
        });

        // Send verification email
        await sendVerificationEmail(email, verificationToken);

        res.status(201).json({ message: 'User registered. Please check backend console for verification link.' });
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
