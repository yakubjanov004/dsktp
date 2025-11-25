CREATE TABLE material_and_technician (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    material_id INTEGER REFERENCES materials(id),
    quantity INTEGER
);