from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from wtforms import (
    StringField,
    PasswordField,
    DateField,
    TimeField,
    IntegerField,
    SubmitField,
    SelectField,
    TextAreaField,
    BooleanField,
    FileField,
    DecimalField,
    RadioField,
)
from wtforms.validators import (
    DataRequired,
    NumberRange,
    Email,
    Length,
    EqualTo,
    Optional,
)

class PassForm(FlaskForm):
    type = StringField('Típus', validators=[DataRequired()])
    start_date = DateField('Kezdő dátum', validators=[DataRequired()])
    end_date = DateField('Lejárati dátum', validators=[DataRequired()])
    total_uses = IntegerField('Alkalmak száma', validators=[DataRequired(), NumberRange(min=1)])
    user_id = SelectField('Felhasználó', coerce=int, validators=[DataRequired()])
    comment = TextAreaField('Megjegyzés')
    submit = SubmitField('Bérlet létrehozása')


class UserForm(FlaskForm):
    username = StringField('Felhasználónév', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    password = StringField('Jelszó', validators=[DataRequired()])
    role = SelectField('Szerep', choices=[('user', 'User'), ('admin', 'Admin')], validators=[DataRequired()])
    submit = SubmitField('Mentés')


class LoginForm(FlaskForm):
    username = StringField('Felhasználónév', validators=[DataRequired()])
    password = PasswordField('Jelszó', validators=[DataRequired()])
    submit = SubmitField('Bejelentkezés')


class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Jelszó elküldése')


class RegistrationForm(FlaskForm):
    username = StringField('Felhasználónév', validators=[DataRequired(), Length(min=3, max=150)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Jelszó', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        'Jelszó megerősítése',
        validators=[DataRequired(), EqualTo('password', message='A jelszavak nem egyeznek.')],
    )
    submit = SubmitField('Regisztráció')


class EmailSettingsForm(FlaskForm):
    email_from = StringField('Feladó email')
    email_password = PasswordField('Email jelszó')

    user_created_enabled = BooleanField('Felhasználó létrehozásakor')
    user_created_text = TextAreaField('Létrehozás üzenete')

    user_deleted_enabled = BooleanField('Felhasználó törlésekor')
    user_deleted_text = TextAreaField('Törlés üzenete')

    pass_created_enabled = BooleanField('Új bérlet létrehozásakor')
    pass_created_text = TextAreaField('Bérlet létrehozás üzenete')

    pass_deleted_enabled = BooleanField('Bérlet törlésekor')
    pass_deleted_text = TextAreaField('Bérlet törlés üzenete')

    pass_used_enabled = BooleanField('Alkalom változásakor')
    pass_used_text = TextAreaField('Alkalom változás üzenete')

    event_signup_user_enabled = BooleanField('Esemény jelentkezéskor (saját)')
    event_signup_user_text = TextAreaField('Saját jelentkezés üzenete')

    event_signup_admin_enabled = BooleanField('Esemény jelentkezéskor (admin)')
    event_signup_admin_text = TextAreaField('Admin jelentkeztetés üzenete')

    event_unregister_user_enabled = BooleanField('Leiratkozáskor (saját)')
    event_unregister_user_text = TextAreaField('Saját leiratkozás üzenete')

    event_unregister_admin_enabled = BooleanField('Leiratkozáskor (admin)')
    event_unregister_admin_text = TextAreaField('Admin leiratkoztatás üzenete')

    submit = SubmitField('Mentés')


class RestoreForm(FlaskForm):
    """Form used for uploading a database backup to restore."""
    backup_file = FileField('Backup fájl', validators=[DataRequired()])
    submit = SubmitField('Visszaállítás')


class EventForm(FlaskForm):
    name = StringField('Esemény neve', validators=[DataRequired()])
    date = DateField('Dátum', validators=[DataRequired()])
    start_time = TimeField('Kezdő időpont', validators=[DataRequired()])
    end_time = TimeField('Vég időpont', validators=[DataRequired()])
    capacity = IntegerField('Létszám', validators=[DataRequired(), NumberRange(min=1)])
    price = DecimalField('Ár (HUF)', places=2, rounding=None, validators=[Optional(), NumberRange(min=0)])
    color = SelectField(
        'Szín',
        choices=[
            ('darkgreen', 'Sötétzöld'),
            ('red', 'Piros'),
            ('blue', 'Kék'),
            ('purple', 'Lila'),
            ('orange', 'Narancs'),
            ('burgundy', 'Bordó'),
            ('darkblue', 'Sötétkék'),
        ],
        default='blue',
        validators=[DataRequired()],
    )
    image = FileField('Kép feltöltése', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Csak kép tölthető fel.')])
    is_final_event = BooleanField('Záró esemény (bérlet nem használható)')
    submit = SubmitField('Mentés')


class PurchasePassForm(FlaskForm):
    pass_type = RadioField(
        'Bérlet típusa',
        choices=[('4', '4 alkalmas'), ('8', '8 alkalmas')],
        default='4',
        validators=[DataRequired()],
    )
    submit = SubmitField('Bérlet igénylése')

