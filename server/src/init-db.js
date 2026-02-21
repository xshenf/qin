const { initDb, User } = require('./db');
const bcrypt = require('bcrypt');

async function runInit() {
    console.log('Initializing database...');
    try {
        await initDb();

        // Optional: Check if admin user exists, if not, create one
        const adminEmail = process.env.ADMIN_EMAIL || 'admin@example.com';
        const adminPassword = process.env.ADMIN_PASSWORD || 'admin123';

        const existingAdmin = await User.findOne({ where: { email: adminEmail } });
        if (!existingAdmin) {
            console.log(`Creating default admin user: ${adminEmail}`);
            const hashedPassword = await bcrypt.hash(adminPassword, 10);
            await User.create({
                email: adminEmail,
                password_hash: hashedPassword,
                role: 'admin',
                is_verified: true
            });
            console.log('Admin user created successfully.');
        } else {
            console.log('Admin user already exists.');
        }

        console.log('Database initialization completed successfully!');
        process.exit(0);
    } catch (error) {
        console.error('Database initialization failed:', error);
        process.exit(1);
    }
}

runInit();
