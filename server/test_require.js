try {
    console.log('Requiring express...');
    require('express');
    console.log('express loaded.');

    console.log('Requiring cors...');
    require('cors');
    console.log('cors loaded.');

    console.log('Requiring sqlite3...');
    require('sqlite3');
    console.log('sqlite3 loaded.');

    console.log('Requiring sequelize...');
    require('sequelize');
    console.log('sequelize loaded.');

    console.log('Requiring bcrypt...');
    require('bcrypt');
    console.log('bcrypt loaded.');
} catch (e) {
    console.error('Error:', e);
}
