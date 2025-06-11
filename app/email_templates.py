def base_email_template(title: str, content: str) -> str:
    return f"""
    <html>
      <body style='font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;'>
        <div style='max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 8px;'>
          <h2 style='color: #2c3e50;'>{title}</h2>
          <p style='color: #333;'>{content}</p>
          <hr>
          <small style='color: #999;'>Ez egy automatikus üzenet a Bérletkezelő Rendszertől.</small>
        </div>
      </body>
    </html>
    """

def registration_email(username: str, password: str) -> str:
    content = f"Kedves {username},<br><br>Felhasználónév: {username}<br>Jelszó: {password}<br>"
    return base_email_template("Fiók létrehozva", content)

def pass_created_email(username: str, pass_type: str, start, end, total) -> str:
    content = f"Bérlet típusa: {pass_type}<br>Érvényesség: {start} - {end}<br>Alkalmak: {total}"
    return base_email_template("Új bérlet létrehozva", content)

def pass_deleted_email(username: str, pass_type: str, start, end, used) -> str:
    content = f"Törölt bérlet: {pass_type}<br>{start} - {end}<br>Felhasználva: {used} alkalom"
    return base_email_template("Bérlet törölve", content)