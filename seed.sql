-- Datos de ejemplo
insert into public.professionals (full_name, specialty) values
('Claudia Torres', 'Terapia Ocupacional'),
('Javiera Jara', 'Fonoaudiología'),
('Paulina Urriola', 'Psicología');

insert into public.services (name, duration_minutes, price) values
('Evaluación 30min', 30, 30000),
('Terapia 30min', 30, 30000),
('Terapia 45min', 45, 42000);

insert into public.patients (full_name, rut, phone, email) values
('Juan Pérez', '12.345.678-9', '+56912345678', 'juan@example.com'),
('María López', '9.876.543-2', '+56987654321', 'maria@example.com');
