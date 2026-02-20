from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import re
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'votre-cle-secrete-changez-moi'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///robotblog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'pdf'}

db = SQLAlchemy(app)

# ─── MODELES ──────────────────────────────────────────────
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    resume = db.Column(db.String(500))
    image_couverture = db.Column(db.String(300))
    categorie = db.Column(db.String(50), default='general')
    jour = db.Column(db.Integer)  # Jour du projet (J1, J2, ...)
    publie = db.Column(db.Boolean, default=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_publication = db.Column(db.DateTime)
    tags = db.Column(db.String(300))  # tags séparés par virgule
    vues = db.Column(db.Integer, default=0)

    def get_tags_list(self):
        if self.tags:
            return [t.strip() for t in self.tags.split(',')]
        return []


class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_fichier = db.Column(db.String(300), nullable=False)
    nom_original = db.Column(db.String(300))
    type_media = db.Column(db.String(50))  # image, video, pdf
    taille = db.Column(db.Integer)
    date_upload = db.Column(db.DateTime, default=datetime.utcnow)


class Ressource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500))
    description = db.Column(db.Text)
    categorie = db.Column(db.String(100))  # composants, logiciels, tutoriels, outils
    ordre = db.Column(db.Integer, default=0)


class Timeline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    date_event = db.Column(db.DateTime)
    statut = db.Column(db.String(50), default='en-cours')  # complete, en-cours, planifie
    icone = db.Column(db.String(50), default='🔧')


# ─── HELPERS ──────────────────────────────────────────────
def slugify(text):
    text = text.lower()
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[ìíîï]', 'i', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    return text

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

CATEGORIES = {
    'journal': 'Journal de bord',
    'mecanique': 'Mécanique',
    'electronique': 'Électronique',
    'programmation': 'Programmation',
    'ia': 'Intelligence Artificielle',
    'tests': 'Tests & Résultats',
    'reflexion': 'Réflexions',
    'ressources': 'Ressources',
}

# ─── ROUTES PUBLIQUES ─────────────────────────────────────
@app.route('/')
def index():
    articles_recents = Article.query.filter_by(publie=True)\
        .order_by(Article.date_publication.desc()).limit(6).all()
    dernier_jour = db.session.query(db.func.max(Article.jour))\
        .filter(Article.publie==True).scalar() or 0
    nb_articles = Article.query.filter_by(publie=True).count()
    return render_template('index.html',
        articles=articles_recents,
        dernier_jour=dernier_jour,
        nb_articles=nb_articles,
        categories=CATEGORIES)

@app.route('/journal')
def journal():
    page = request.args.get('page', 1, type=int)
    articles = Article.query.filter_by(publie=True)\
        .order_by(Article.jour.desc(), Article.date_publication.desc())\
        .paginate(page=page, per_page=9, error_out=False)
    return render_template('journal.html', articles=articles, categories=CATEGORIES)

@app.route('/categorie/<cat>')
def categorie(cat):
    page = request.args.get('page', 1, type=int)
    articles = Article.query.filter_by(publie=True, categorie=cat)\
        .order_by(Article.date_publication.desc())\
        .paginate(page=page, per_page=9, error_out=False)
    nom_cat = CATEGORIES.get(cat, cat)
    return render_template('categorie.html', articles=articles, cat=cat, nom_cat=nom_cat, categories=CATEGORIES)

@app.route('/article/<slug>')
def article(slug):
    art = Article.query.filter_by(slug=slug, publie=True).first_or_404()
    art.vues += 1
    db.session.commit()
    # Articles précédent/suivant
    precedent = Article.query.filter(
        Article.publie==True, Article.jour < art.jour
    ).order_by(Article.jour.desc()).first() if art.jour else None
    suivant = Article.query.filter(
        Article.publie==True, Article.jour > art.jour
    ).order_by(Article.jour.asc()).first() if art.jour else None
    return render_template('article.html', article=art, precedent=precedent, suivant=suivant)

@app.route('/timeline')
def timeline():
    etapes = Timeline.query.order_by(Timeline.date_event.asc()).all()
    return render_template('timeline.html', etapes=etapes)

@app.route('/ressources')
def ressources():
    toutes = Ressource.query.order_by(Ressource.categorie, Ressource.ordre).all()
    par_cat = {}
    for r in toutes:
        par_cat.setdefault(r.categorie, []).append(r)
    return render_template('ressources.html', ressources_par_cat=par_cat)

@app.route('/a-propos')
def a_propos():
    return render_template('a_propos.html')

@app.route('/recherche')
def recherche():
    q = request.args.get('q', '')
    articles = []
    if q:
        like = f'%{q}%'
        articles = Article.query.filter(
            Article.publie==True,
            (Article.titre.like(like)) | (Article.contenu.like(like)) | (Article.tags.like(like))
        ).order_by(Article.date_publication.desc()).all()
    return render_template('recherche.html', articles=articles, q=q)

# ─── ADMINISTRATION ────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if (request.form.get('username') == 'admin' and
            request.form.get('password') == 'robot2024'):  # Changez ce mot de passe !
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Identifiants incorrects', 'danger')
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_dashboard():
    nb_articles = Article.query.count()
    nb_publies = Article.query.filter_by(publie=True).count()
    nb_medias = Media.query.count()
    articles_recents = Article.query.order_by(Article.date_creation.desc()).limit(5).all()
    return render_template('admin/dashboard.html',
        nb_articles=nb_articles, nb_publies=nb_publies,
        nb_medias=nb_medias, articles_recents=articles_recents)

@app.route('/admin/articles')
@login_required
def admin_articles():
    articles = Article.query.order_by(Article.date_creation.desc()).all()
    return render_template('admin/articles.html', articles=articles, categories=CATEGORIES)

@app.route('/admin/article/nouveau', methods=['GET', 'POST'])
@login_required
def admin_nouvel_article():
    if request.method == 'POST':
        titre = request.form.get('titre', '').strip()
        if not titre:
            flash('Le titre est requis', 'danger')
            return render_template('admin/article_form.html', categories=CATEGORIES)
        
        slug_base = slugify(titre)
        slug = slug_base
        counter = 1
        while Article.query.filter_by(slug=slug).first():
            slug = f"{slug_base}-{counter}"
            counter += 1

        # Gestion image couverture
        image_couverture = None
        if 'image_couverture' in request.files:
            f = request.files['image_couverture']
            if f and f.filename and allowed_file(f.filename):
                fname = secure_filename(f.filename)
                fname = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{fname}"
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                image_couverture = fname

        publie = 'publie' in request.form
        art = Article(
            titre=titre,
            slug=slug,
            contenu=request.form.get('contenu', ''),
            resume=request.form.get('resume', ''),
            image_couverture=image_couverture,
            categorie=request.form.get('categorie', 'journal'),
            jour=request.form.get('jour') or None,
            tags=request.form.get('tags', ''),
            publie=publie,
            date_publication=datetime.utcnow() if publie else None,
        )
        db.session.add(art)
        db.session.commit()
        flash('Article créé avec succès !', 'success')
        return redirect(url_for('admin_articles'))

    return render_template('admin/article_form.html', article=None, categories=CATEGORIES)

@app.route('/admin/article/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def admin_modifier_article(id):
    art = Article.query.get_or_404(id)
    if request.method == 'POST':
        art.titre = request.form.get('titre', '').strip()
        art.contenu = request.form.get('contenu', '')
        art.resume = request.form.get('resume', '')
        art.categorie = request.form.get('categorie', 'journal')
        art.jour = request.form.get('jour') or None
        art.tags = request.form.get('tags', '')
        
        if 'image_couverture' in request.files:
            f = request.files['image_couverture']
            if f and f.filename and allowed_file(f.filename):
                fname = secure_filename(f.filename)
                fname = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{fname}"
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                art.image_couverture = fname

        etait_publie = art.publie
        art.publie = 'publie' in request.form
        if art.publie and not etait_publie:
            art.date_publication = datetime.utcnow()
        
        db.session.commit()
        flash('Article mis à jour !', 'success')
        return redirect(url_for('admin_articles'))
    
    return render_template('admin/article_form.html', article=art, categories=CATEGORIES)

@app.route('/admin/article/<int:id>/supprimer', methods=['POST'])
@login_required
def admin_supprimer_article(id):
    art = Article.query.get_or_404(id)
    db.session.delete(art)
    db.session.commit()
    flash('Article supprimé', 'info')
    return redirect(url_for('admin_articles'))

@app.route('/admin/medias', methods=['GET', 'POST'])
@login_required
def admin_medias():
    if request.method == 'POST':
        if 'fichier' not in request.files:
            flash('Aucun fichier sélectionné', 'danger')
        else:
            f = request.files['fichier']
            if f and allowed_file(f.filename):
                nom_original = f.filename
                fname = secure_filename(f.filename)
                fname = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{fname}"
                path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
                f.save(path)
                ext = fname.rsplit('.', 1)[1].lower()
                type_media = 'image' if ext in {'png','jpg','jpeg','gif','webp'} else \
                             'video' if ext == 'mp4' else 'pdf'
                media = Media(
                    nom_fichier=fname,
                    nom_original=nom_original,
                    type_media=type_media,
                    taille=os.path.getsize(path)
                )
                db.session.add(media)
                db.session.commit()
                flash(f'Fichier "{nom_original}" uploadé !', 'success')
    
    medias = Media.query.order_by(Media.date_upload.desc()).all()
    return render_template('admin/medias.html', medias=medias)

@app.route('/admin/medias/<int:id>/supprimer', methods=['POST'])
@login_required
def admin_supprimer_media(id):
    media = Media.query.get_or_404(id)
    path = os.path.join(app.config['UPLOAD_FOLDER'], media.nom_fichier)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(media)
    db.session.commit()
    flash('Fichier supprimé', 'info')
    return redirect(url_for('admin_medias'))

@app.route('/admin/timeline', methods=['GET', 'POST'])
@login_required
def admin_timeline():
    if request.method == 'POST':
        etape = Timeline(
            titre=request.form.get('titre', ''),
            description=request.form.get('description', ''),
            date_event=datetime.strptime(request.form.get('date_event'), '%Y-%m-%d') if request.form.get('date_event') else None,
            statut=request.form.get('statut', 'planifie'),
            icone=request.form.get('icone', '🔧'),
        )
        db.session.add(etape)
        db.session.commit()
        flash('Étape ajoutée !', 'success')
    etapes = Timeline.query.order_by(Timeline.date_event.asc()).all()
    return render_template('admin/timeline.html', etapes=etapes)

@app.route('/admin/timeline/<int:id>/supprimer', methods=['POST'])
@login_required
def admin_supprimer_etape(id):
    etape = Timeline.query.get_or_404(id)
    db.session.delete(etape)
    db.session.commit()
    flash('Étape supprimée', 'info')
    return redirect(url_for('admin_timeline'))

@app.route('/admin/ressources', methods=['GET', 'POST'])
@login_required
def admin_ressources():
    if request.method == 'POST':
        r = Ressource(
            titre=request.form.get('titre', ''),
            url=request.form.get('url', ''),
            description=request.form.get('description', ''),
            categorie=request.form.get('categorie', 'outils'),
            ordre=request.form.get('ordre', 0),
        )
        db.session.add(r)
        db.session.commit()
        flash('Ressource ajoutée !', 'success')
    ressources = Ressource.query.order_by(Ressource.categorie, Ressource.ordre).all()
    return render_template('admin/ressources.html', ressources=ressources)

@app.route('/admin/ressources/<int:id>/supprimer', methods=['POST'])
@login_required
def admin_supprimer_ressource(id):
    r = Ressource.query.get_or_404(id)
    db.session.delete(r)
    db.session.commit()
    return redirect(url_for('admin_ressources'))

# Filtre Jinja pour formater les dates
@app.template_filter('date_fr')
def date_fr(dt):
    if not dt:
        return ''
    mois = ['jan','fév','mar','avr','mai','juin','juil','août','sep','oct','nov','déc']
    return f"{dt.day} {mois[dt.month-1]} {dt.year}"

@app.template_filter('taille_fichier')
def taille_fichier(taille):
    if taille < 1024:
        return f"{taille} o"
    elif taille < 1024*1024:
        return f"{taille//1024} Ko"
    return f"{taille//(1024*1024)} Mo"

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
        # Données de démo si la DB est vide
        if Article.query.count() == 0:
            demo = Article(
                titre="Jour 1 – Le projet commence !",
                slug="jour-1-le-projet-commence",
                contenu="""<h2>🚀 Le grand départ</h2>
<p>Aujourd'hui marque le début d'une aventure extraordinaire : construire un robot humanoïde de A à Z.</p>
<p>L'objectif à long terme est de créer un robot bipède capable de marcher, d'interagir avec son environnement et peut-être un jour de m'assister dans des tâches quotidiennes.</p>
<h2>📋 Le plan du projet</h2>
<p>J'ai défini les grandes étapes :</p>
<ul>
  <li><strong>Phase 1</strong> – Architecture et conception (J1 → J30)</li>
  <li><strong>Phase 2</strong> – Structure mécanique (J31 → J90)</li>
  <li><strong>Phase 3</strong> – Électronique et capteurs (J91 → J150)</li>
  <li><strong>Phase 4</strong> – Programmation et IA (J151 → J240)</li>
  <li><strong>Phase 5</strong> – Tests et intégration (J241 → J300)</li>
</ul>
<h2>🛠️ Matériel envisagé</h2>
<p>Pour commencer, j'explore les options : servomoteurs Dynamixel, Raspberry Pi 5, capteurs IMU, OpenCV pour la vision...</p>
<p>Ce blog sera mon carnet de bord jour par jour. Rejoignez-moi dans cette aventure !</p>""",
                resume="Le premier jour du projet : définition des objectifs, plan de route et premiers choix techniques pour construire un robot humanoïde.",
                categorie="journal",
                jour=1,
                tags="démarrage, planification, humanoïde",
                publie=True,
                date_publication=datetime.utcnow(),
            )
            db.session.add(demo)

            etapes = [
                Timeline(titre="Lancement du projet", description="Définition des objectifs et recherche documentaire", statut="complete", icone="🚀", date_event=datetime(2024,1,1)),
                Timeline(titre="Conception mécanique", description="Design de la structure, choix des actionneurs", statut="en-cours", icone="🔧", date_event=datetime(2024,2,1)),
                Timeline(titre="Prototype du torse", description="Impression 3D et assemblage du torse", statut="planifie", icone="🦾", date_event=datetime(2024,4,1)),
                Timeline(titre="Électronique & capteurs", description="Câblage, IMU, caméras, microcontrôleurs", statut="planifie", icone="⚡", date_event=datetime(2024,6,1)),
                Timeline(titre="Locomotion bipède", description="Algorithmes d'équilibre et de marche", statut="planifie", icone="🦿", date_event=datetime(2024,9,1)),
                Timeline(titre="IA & interaction", description="Vision par ordinateur, NLP, prise de décision", statut="planifie", icone="🧠", date_event=datetime(2024,11,1)),
            ]
            for e in etapes:
                db.session.add(e)

            ressources_demo = [
                Ressource(titre="Dynamixel Servos", url="https://www.robotis.com/shop/list.php?ca_id=101021", description="Servomoteurs intelligents utilisés dans de nombreux robots humanoïdes", categorie="composants"),
                Ressource(titre="Raspberry Pi", url="https://www.raspberrypi.com/", description="Ordinateur monocarte pour le cerveau du robot", categorie="composants"),
                Ressource(titre="ROS2 (Robot Operating System)", url="https://docs.ros.org/en/humble/", description="Framework incontournable pour la robotique", categorie="logiciels"),
                Ressource(titre="OpenCV", url="https://opencv.org/", description="Bibliothèque de vision par ordinateur", categorie="logiciels"),
                Ressource(titre="Poppy Project", url="https://www.poppy-project.org/", description="Robot humanoïde open-source imprimable en 3D", categorie="inspiration"),
                Ressource(titre="Arduino", url="https://www.arduino.cc/", description="Microcontrôleur pour le contrôle bas niveau", categorie="composants"),
            ]
            for r in ressources_demo:
                db.session.add(r)

            db.session.commit()
    app.run(debug=True)
