import os
import oracledb
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

def get_connection():
    """
    Establish a connection to the Oracle Database in Thin mode.
    Reads credentials strictly from environment variables.
    """
    user = os.getenv("DB_USER", "SYSTEM")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", 1521))
    service_name = os.getenv("DB_SERVICE_NAME", "FREE")

    if not password:
        raise ValueError("Database password is not configured. Please set DB_PASSWORD in your .env file.")

    dsn = f"{host}:{port}/{service_name}"
    return oracledb.connect(user=user, password=password, dsn=dsn)

def test_connection():
    """
    Test the Oracle connection safely without exposing credentials.
    Returns (status: bool, message: str).
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM DUAL")
                cursor.fetchone()
        return True, "Successfully connected to Oracle Database."
    except Exception as e:
        return False, str(e)

def execute_read_query(query, params=None):
    """
    Safely execute a read-only parameterized SELECT query and return rows as list of dicts.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params or {})
            if cursor.description is None:
                return []
            columns = [col[0] for col in cursor.description]
            cursor.rowfactory = lambda *args: dict(zip(columns, args))
            return cursor.fetchall()

def execute_read_scalar_row(query, params=None, default=None):
    """
    Safely execute a read-only query returning a single metrics row as dict.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params or {})
            if cursor.description is None:
                return default or {}
            columns = [col[0] for col in cursor.description]
            cursor.rowfactory = lambda *args: dict(zip(columns, args))
            row = cursor.fetchone()
            return row if row else (default or {})

# ==============================================================================
# Filter Options Retrieval (Dynamically Queried from Live Oracle Tables)
# ==============================================================================

def get_filter_departments():
    """Get all departments for filter dropdowns."""
    return execute_read_query("SELECT DEPT_ID, DEPT_NAME FROM DEPARTMENT1143 ORDER BY DEPT_NAME")

def get_filter_universities():
    """Get all universities for filter dropdowns."""
    return execute_read_query("SELECT UNID, UNAME FROM UNIVERSITY1143 ORDER BY UNAME")

def get_filter_locations():
    """Get distinct university campus locations."""
    rows = execute_read_query("SELECT DISTINCT LOCATION FROM UNIVERSITY1143 WHERE LOCATION IS NOT NULL ORDER BY LOCATION")
    return [r["LOCATION"] for r in rows if r.get("LOCATION")]

def get_filter_faculty_designations():
    """Get distinct faculty designations."""
    rows = execute_read_query("SELECT DISTINCT DESIGNATION FROM FACULTY1143 WHERE DESIGNATION IS NOT NULL ORDER BY DESIGNATION")
    return [r["DESIGNATION"] for r in rows if r.get("DESIGNATION")]

def get_filter_faculty_members():
    """Get faculty members list for course assignment filters."""
    return execute_read_query("SELECT FID, FNAME FROM FACULTY1143 ORDER BY FNAME")

def get_filter_courses():
    """Get course list for examination filters."""
    return execute_read_query("SELECT COURSE_ID, COURSE_NAME FROM COURSE1143 ORDER BY COURSE_NAME")

def get_filter_exam_dates():
    """Get distinct scheduled exam dates formatted as YYYY-MM-DD."""
    rows = execute_read_query("SELECT DISTINCT TO_CHAR(EXAM_DATE, 'YYYY-MM-DD') AS EXAM_DATE FROM EXAM1143 ORDER BY 1")
    return [r["EXAM_DATE"] for r in rows if r.get("EXAM_DATE")]

def get_filter_result_grades():
    """Get distinct grades from results table."""
    rows = execute_read_query("SELECT DISTINCT TRIM(GRADE) AS GRADE FROM RESULT1143 WHERE GRADE IS NOT NULL ORDER BY 1")
    return [r["GRADE"] for r in rows if r.get("GRADE")]

def get_filter_library_authors():
    """Get distinct book authors from library table."""
    rows = execute_read_query("SELECT DISTINCT AUTHOR FROM LIBRARY1143 WHERE AUTHOR IS NOT NULL ORDER BY AUTHOR")
    return [r["AUTHOR"] for r in rows if r.get("AUTHOR")]

# ==============================================================================
# Record Queries with Enhanced Multi-Column Search & Filter Criteria
# ==============================================================================

def get_students(search_term=None, dept_id=None, gender=None):
    """
    Retrieve student records with multi-column search and optional department/gender filters.
    """
    base_query = """
        SELECT 
            s.SID,
            s.SNAME,
            TO_CHAR(s.DOB, 'YYYY-MM-DD') AS DOB,
            s.GENDER,
            s.ADDRESS,
            s.DEPT_ID,
            NVL(d.DEPT_NAME, 'Unassigned') AS DEPT_NAME
        FROM STUDENT1143 s
        LEFT JOIN DEPARTMENT1143 d ON s.DEPT_ID = d.DEPT_ID
        WHERE 1=1
    """
    params = {}
    if search_term and search_term.strip():
        base_query += """ AND (
            TO_CHAR(s.SID) LIKE :search 
            OR UPPER(s.SNAME) LIKE :search 
            OR UPPER(s.ADDRESS) LIKE :search 
            OR UPPER(d.DEPT_NAME) LIKE :search
        )"""
        params["search"] = f"%{search_term.strip().upper()}%"

    if dept_id and str(dept_id).strip():
        base_query += " AND s.DEPT_ID = :dept_id"
        params["dept_id"] = int(dept_id)

    if gender and str(gender).strip():
        base_query += " AND s.GENDER = :gender"
        params["gender"] = str(gender).strip().upper()

    base_query += " ORDER BY s.SID"
    return execute_read_query(base_query, params)

def get_student_stats():
    """Retrieve summary metrics for student records view."""
    stats_query = """
        SELECT 
            (SELECT COUNT(*) FROM STUDENT1143) AS total_students,
            (SELECT COUNT(*) FROM DEPARTMENT1143) AS total_departments
        FROM DUAL
    """
    return execute_read_scalar_row(stats_query, default={"TOTAL_STUDENTS": 0, "TOTAL_DEPARTMENTS": 0})

def get_universities(search_term=None, location=None):
    """
    Retrieve university records with multi-column search and location filter.
    """
    base_query = """
        SELECT 
            u.UNID, 
            u.UNAME, 
            u.LOCATION
        FROM UNIVERSITY1143 u
        WHERE 1=1
    """
    params = {}
    if search_term and search_term.strip():
        base_query += """ AND (
            TO_CHAR(u.UNID) LIKE :search 
            OR UPPER(u.UNAME) LIKE :search 
            OR UPPER(u.LOCATION) LIKE :search
        )"""
        params["search"] = f"%{search_term.strip().upper()}%"

    if location and str(location).strip():
        base_query += " AND UPPER(u.LOCATION) = UPPER(:location)"
        params["location"] = str(location).strip()

    base_query += " ORDER BY u.UNID"
    return execute_read_query(base_query, params)

def get_university_stats():
    """Retrieve summary metrics for the university view."""
    query = """
        SELECT 
            (SELECT COUNT(*) FROM UNIVERSITY1143) AS total_universities,
            (SELECT COUNT(DISTINCT LOCATION) FROM UNIVERSITY1143) AS total_locations
        FROM DUAL
    """
    return execute_read_scalar_row(query, default={"TOTAL_UNIVERSITIES": 0, "TOTAL_LOCATIONS": 0})

def get_departments(search_term=None, unid=None):
    """
    Retrieve department records with multi-column search and parent university filter.
    """
    base_query = """
        SELECT 
            d.DEPT_ID, 
            d.DEPT_NAME, 
            d.UNID, 
            NVL(u.UNAME, 'Unassigned') AS UNIVERSITY_NAME
        FROM DEPARTMENT1143 d
        LEFT JOIN UNIVERSITY1143 u ON d.UNID = u.UNID
        WHERE 1=1
    """
    params = {}
    if search_term and search_term.strip():
        base_query += """ AND (
            TO_CHAR(d.DEPT_ID) LIKE :search 
            OR UPPER(d.DEPT_NAME) LIKE :search 
            OR UPPER(u.UNAME) LIKE :search
        )"""
        params["search"] = f"%{search_term.strip().upper()}%"

    if unid and str(unid).strip():
        base_query += " AND d.UNID = :unid"
        params["unid"] = int(unid)

    base_query += " ORDER BY d.DEPT_ID"
    return execute_read_query(base_query, params)

def get_department_stats():
    """Retrieve summary metrics for the departments view."""
    query = """
        SELECT 
            (SELECT COUNT(*) FROM DEPARTMENT1143) AS total_departments,
            (SELECT COUNT(DISTINCT UNID) FROM DEPARTMENT1143) AS affiliated_universities
        FROM DUAL
    """
    return execute_read_scalar_row(query, default={"TOTAL_DEPARTMENTS": 0, "AFFILIATED_UNIVERSITIES": 0})

def get_faculty(search_term=None, dept_id=None, designation=None):
    """
    Retrieve faculty records with multi-column search and department/designation filters.
    """
    base_query = """
        SELECT 
            f.FID, 
            f.FNAME, 
            f.DESIGNATION, 
            f.SALARY, 
            f.DEPT_ID, 
            NVL(d.DEPT_NAME, 'Unassigned') AS DEPT_NAME
        FROM FACULTY1143 f
        LEFT JOIN DEPARTMENT1143 d ON f.DEPT_ID = d.DEPT_ID
        WHERE 1=1
    """
    params = {}
    if search_term and search_term.strip():
        base_query += """ AND (
            TO_CHAR(f.FID) LIKE :search 
            OR UPPER(f.FNAME) LIKE :search 
            OR UPPER(f.DESIGNATION) LIKE :search 
            OR UPPER(d.DEPT_NAME) LIKE :search
        )"""
        params["search"] = f"%{search_term.strip().upper()}%"

    if dept_id and str(dept_id).strip():
        base_query += " AND f.DEPT_ID = :dept_id"
        params["dept_id"] = int(dept_id)

    if designation and str(designation).strip():
        base_query += " AND UPPER(f.DESIGNATION) = UPPER(:designation)"
        params["designation"] = str(designation).strip()

    base_query += " ORDER BY f.FID"
    return execute_read_query(base_query, params)

def get_faculty_stats():
    """Retrieve summary metrics for the faculty view."""
    query = """
        SELECT 
            (SELECT COUNT(*) FROM FACULTY1143) AS total_faculty,
            (SELECT COUNT(DISTINCT DEPT_ID) FROM FACULTY1143) AS total_departments,
            (SELECT NVL(ROUND(AVG(SALARY), 2), 0) FROM FACULTY1143) AS avg_salary
        FROM DUAL
    """
    return execute_read_scalar_row(query, default={"TOTAL_FACULTY": 0, "TOTAL_DEPARTMENTS": 0, "AVG_SALARY": 0})

def get_courses(search_term=None, dept_id=None, fid=None):
    """
    Retrieve course records with multi-column search and department/instructor filters.
    """
    base_query = """
        SELECT 
            c.COURSE_ID, 
            c.COURSE_NAME, 
            c.CREDITS, 
            c.DEPT_ID, 
            NVL(d.DEPT_NAME, 'Unassigned') AS DEPT_NAME, 
            c.FID, 
            NVL(f.FNAME, 'Unassigned') AS FACULTY_NAME
        FROM COURSE1143 c
        LEFT JOIN DEPARTMENT1143 d ON c.DEPT_ID = d.DEPT_ID
        LEFT JOIN FACULTY1143 f ON c.FID = f.FID
        WHERE 1=1
    """
    params = {}
    if search_term and search_term.strip():
        base_query += """ AND (
            TO_CHAR(c.COURSE_ID) LIKE :search 
            OR UPPER(c.COURSE_NAME) LIKE :search 
            OR TO_CHAR(c.CREDITS) LIKE :search
            OR UPPER(d.DEPT_NAME) LIKE :search 
            OR UPPER(f.FNAME) LIKE :search
        )"""
        params["search"] = f"%{search_term.strip().upper()}%"

    if dept_id and str(dept_id).strip():
        base_query += " AND c.DEPT_ID = :dept_id"
        params["dept_id"] = int(dept_id)

    if fid and str(fid).strip():
        base_query += " AND c.FID = :fid"
        params["fid"] = int(fid)

    base_query += " ORDER BY c.COURSE_ID"
    return execute_read_query(base_query, params)

def get_course_stats():
    """Retrieve summary metrics for the courses view."""
    query = """
        SELECT 
            (SELECT COUNT(*) FROM COURSE1143) AS total_courses,
            (SELECT NVL(SUM(CREDITS), 0) FROM COURSE1143) AS total_credits,
            (SELECT COUNT(DISTINCT FID) FROM COURSE1143) AS teaching_faculty
        FROM DUAL
    """
    return execute_read_scalar_row(query, default={"TOTAL_COURSES": 0, "TOTAL_CREDITS": 0, "TEACHING_FACULTY": 0})

def get_classrooms(search_term=None, dept_id=None, min_capacity=None):
    """
    Retrieve classroom records with search across room/capacity/dept and filters.
    """
    base_query = """
        SELECT 
            cl.ROOM_NO, 
            cl.CAPACITY, 
            cl.DEPT_ID, 
            NVL(d.DEPT_NAME, 'Unassigned') AS DEPT_NAME
        FROM CLASSROOM1143 cl
        LEFT JOIN DEPARTMENT1143 d ON cl.DEPT_ID = d.DEPT_ID
        WHERE 1=1
    """
    params = {}
    if search_term and search_term.strip():
        base_query += """ AND (
            TO_CHAR(cl.ROOM_NO) LIKE :search 
            OR TO_CHAR(cl.CAPACITY) LIKE :search 
            OR UPPER(d.DEPT_NAME) LIKE :search
        )"""
        params["search"] = f"%{search_term.strip().upper()}%"

    if dept_id and str(dept_id).strip():
        base_query += " AND cl.DEPT_ID = :dept_id"
        params["dept_id"] = int(dept_id)

    if min_capacity and str(min_capacity).strip():
        base_query += " AND cl.CAPACITY >= :min_capacity"
        params["min_capacity"] = int(min_capacity)

    base_query += " ORDER BY cl.ROOM_NO"
    return execute_read_query(base_query, params)

def get_classroom_stats():
    """Retrieve summary metrics for classrooms view."""
    query = """
        SELECT 
            (SELECT COUNT(*) FROM CLASSROOM1143) AS total_rooms,
            (SELECT NVL(SUM(CAPACITY), 0) FROM CLASSROOM1143) AS total_capacity,
            (SELECT COUNT(DISTINCT DEPT_ID) FROM CLASSROOM1143) AS total_departments
        FROM DUAL
    """
    return execute_read_scalar_row(query, default={"TOTAL_ROOMS": 0, "TOTAL_CAPACITY": 0, "TOTAL_DEPARTMENTS": 0})

def get_exams(search_term=None, course_id=None, exam_date=None):
    """
    Retrieve exam records with search across ID/name/course/room and course/date filters.
    """
    base_query = """
        SELECT 
            e.EXAM_ID, 
            e.EXAM_NAME, 
            TO_CHAR(e.EXAM_DATE, 'YYYY-MM-DD') AS EXAM_DATE, 
            e.COURSE_ID, 
            NVL(c.COURSE_NAME, 'Unassigned') AS COURSE_NAME, 
            e.ROOM_NO
        FROM EXAM1143 e
        LEFT JOIN COURSE1143 c ON e.COURSE_ID = c.COURSE_ID
        WHERE 1=1
    """
    params = {}
    if search_term and search_term.strip():
        base_query += """ AND (
            TO_CHAR(e.EXAM_ID) LIKE :search 
            OR UPPER(e.EXAM_NAME) LIKE :search 
            OR UPPER(c.COURSE_NAME) LIKE :search 
            OR TO_CHAR(e.ROOM_NO) LIKE :search
        )"""
        params["search"] = f"%{search_term.strip().upper()}%"

    if course_id and str(course_id).strip():
        base_query += " AND e.COURSE_ID = :course_id"
        params["course_id"] = int(course_id)

    if exam_date and str(exam_date).strip():
        base_query += " AND TO_CHAR(e.EXAM_DATE, 'YYYY-MM-DD') = :exam_date"
        params["exam_date"] = str(exam_date).strip()

    base_query += " ORDER BY e.EXAM_ID"
    return execute_read_query(base_query, params)

def get_exam_stats():
    """Retrieve summary metrics for examinations view."""
    query = """
        SELECT 
            (SELECT COUNT(*) FROM EXAM1143) AS total_exams,
            (SELECT COUNT(DISTINCT COURSE_ID) FROM EXAM1143) AS active_courses,
            (SELECT COUNT(DISTINCT ROOM_NO) FROM EXAM1143) AS rooms_utilized
        FROM DUAL
    """
    return execute_read_scalar_row(query, default={"TOTAL_EXAMS": 0, "ACTIVE_COURSES": 0, "ROOMS_UTILIZED": 0})

def get_results(search_term=None, grade=None, min_marks=None):
    """
    Retrieve result records with multi-column search and grade/marks threshold filters.
    """
    base_query = """
        SELECT 
            r.RESULT_ID, 
            TRIM(r.GRADE) AS GRADE, 
            r.MARKS, 
            r.SID, 
            NVL(s.SNAME, 'Unknown') AS STUDENT_NAME, 
            r.EXAM_ID, 
            NVL(e.EXAM_NAME, 'Unknown') AS EXAM_NAME
        FROM RESULT1143 r
        LEFT JOIN STUDENT1143 s ON r.SID = s.SID
        LEFT JOIN EXAM1143 e ON r.EXAM_ID = e.EXAM_ID
        WHERE 1=1
    """
    params = {}
    if search_term and search_term.strip():
        base_query += """ AND (
            TO_CHAR(r.RESULT_ID) LIKE :search 
            OR UPPER(TRIM(r.GRADE)) LIKE :search 
            OR TO_CHAR(r.MARKS) LIKE :search 
            OR TO_CHAR(r.SID) LIKE :search 
            OR UPPER(s.SNAME) LIKE :search 
            OR UPPER(e.EXAM_NAME) LIKE :search
        )"""
        params["search"] = f"%{search_term.strip().upper()}%"

    if grade and str(grade).strip():
        base_query += " AND UPPER(TRIM(r.GRADE)) = UPPER(:grade)"
        params["grade"] = str(grade).strip()

    if min_marks and str(min_marks).strip():
        base_query += " AND r.MARKS >= :min_marks"
        params["min_marks"] = int(min_marks)

    base_query += " ORDER BY r.RESULT_ID"
    return execute_read_query(base_query, params)

def get_result_stats():
    """Retrieve summary metrics for results view."""
    query = """
        SELECT 
            (SELECT COUNT(*) FROM RESULT1143) AS total_results,
            (SELECT NVL(MAX(MARKS), 0) FROM RESULT1143) AS max_marks,
            (SELECT NVL(ROUND(AVG(MARKS), 1), 0) FROM RESULT1143) AS avg_marks
        FROM DUAL
    """
    return execute_read_scalar_row(query, default={"TOTAL_RESULTS": 0, "MAX_MARKS": 0, "AVG_MARKS": 0})

def get_library(search_term=None, unid=None, author=None):
    """
    Retrieve library book records with search across book ID/title/author/campus and filters.
    """
    base_query = """
        SELECT 
            l.BOOK_ID, 
            l.TITLE, 
            l.AUTHOR, 
            l.UNID, 
            NVL(u.UNAME, 'Unassigned') AS UNIVERSITY_NAME
        FROM LIBRARY1143 l
        LEFT JOIN UNIVERSITY1143 u ON l.UNID = u.UNID
        WHERE 1=1
    """
    params = {}
    if search_term and search_term.strip():
        base_query += """ AND (
            TO_CHAR(l.BOOK_ID) LIKE :search 
            OR UPPER(l.TITLE) LIKE :search 
            OR UPPER(l.AUTHOR) LIKE :search 
            OR UPPER(u.UNAME) LIKE :search
        )"""
        params["search"] = f"%{search_term.strip().upper()}%"

    if unid and str(unid).strip():
        base_query += " AND l.UNID = :unid"
        params["unid"] = int(unid)

    if author and str(author).strip():
        base_query += " AND UPPER(l.AUTHOR) = UPPER(:author)"
        params["author"] = str(author).strip()

    base_query += " ORDER BY l.BOOK_ID"
    return execute_read_query(base_query, params)

def get_library_stats():
    """Retrieve summary metrics for library view."""
    query = """
        SELECT 
            (SELECT COUNT(*) FROM LIBRARY1143) AS total_books,
            (SELECT COUNT(DISTINCT AUTHOR) FROM LIBRARY1143) AS unique_authors,
            (SELECT COUNT(DISTINCT UNID) FROM LIBRARY1143) AS campus_libraries
        FROM DUAL
    """
    return execute_read_scalar_row(query, default={"TOTAL_BOOKS": 0, "UNIQUE_AUTHORS": 0, "CAMPUS_LIBRARIES": 0})

def get_hostels(search_term=None, unid=None, min_capacity=None):
    """
    Retrieve hostel records with search across ID/name/capacity/campus and filters.
    """
    base_query = """
        SELECT 
            h.HOSTEL_ID, 
            h.HOSTEL_NAME, 
            h.CAPACITY, 
            h.UNID, 
            NVL(u.UNAME, 'Unassigned') AS UNIVERSITY_NAME
        FROM HOSTEL1143 h
        LEFT JOIN UNIVERSITY1143 u ON h.UNID = u.UNID
        WHERE 1=1
    """
    params = {}
    if search_term and search_term.strip():
        base_query += """ AND (
            TO_CHAR(h.HOSTEL_ID) LIKE :search 
            OR UPPER(h.HOSTEL_NAME) LIKE :search 
            OR TO_CHAR(h.CAPACITY) LIKE :search
            OR UPPER(u.UNAME) LIKE :search
        )"""
        params["search"] = f"%{search_term.strip().upper()}%"

    if unid and str(unid).strip():
        base_query += " AND h.UNID = :unid"
        params["unid"] = int(unid)

    if min_capacity and str(min_capacity).strip():
        base_query += " AND h.CAPACITY >= :min_capacity"
        params["min_capacity"] = int(min_capacity)

    base_query += " ORDER BY h.HOSTEL_ID"
    return execute_read_query(base_query, params)

def get_hostel_stats():
    """Retrieve summary metrics for hostel view."""
    query = """
        SELECT 
            (SELECT COUNT(*) FROM HOSTEL1143) AS total_hostels,
            (SELECT NVL(SUM(CAPACITY), 0) FROM HOSTEL1143) AS total_capacity,
            (SELECT COUNT(DISTINCT UNID) FROM HOSTEL1143) AS campuses_served
        FROM DUAL
    """
    return execute_read_scalar_row(query, default={"TOTAL_HOSTELS": 0, "TOTAL_CAPACITY": 0, "CAMPUSES_SERVED": 0})

def get_dashboard_stats():
    """Retrieve overview counts across all 10 academic tables for the dashboard."""
    query = """
        SELECT 
            (SELECT COUNT(*) FROM UNIVERSITY1143) AS total_universities,
            (SELECT COUNT(*) FROM DEPARTMENT1143) AS total_departments,
            (SELECT COUNT(*) FROM FACULTY1143) AS total_faculty,
            (SELECT COUNT(*) FROM STUDENT1143) AS total_students,
            (SELECT COUNT(*) FROM COURSE1143) AS total_courses,
            (SELECT COUNT(*) FROM CLASSROOM1143) AS total_classrooms,
            (SELECT COUNT(*) FROM EXAM1143) AS total_exams,
            (SELECT COUNT(*) FROM RESULT1143) AS total_results,
            (SELECT COUNT(*) FROM LIBRARY1143) AS total_books,
            (SELECT COUNT(*) FROM HOSTEL1143) AS total_hostels
        FROM DUAL
    """
    return execute_read_scalar_row(query, default={
        "TOTAL_UNIVERSITIES": 0,
        "TOTAL_DEPARTMENTS": 0,
        "TOTAL_FACULTY": 0,
        "TOTAL_STUDENTS": 0,
        "TOTAL_COURSES": 0,
        "TOTAL_CLASSROOMS": 0,
        "TOTAL_EXAMS": 0,
        "TOTAL_RESULTS": 0,
        "TOTAL_BOOKS": 0,
        "TOTAL_HOSTELS": 0
    })

def get_analytics_dashboard_data():
    """
    Retrieve comprehensive aggregated analytics metrics across all 10 academic tables.
    Includes:
        - 10 entity count cards
        - Students by department
        - Faculty and courses by department
        - Result grade distribution
        - Examination density by course
        - University-wise department counts
        - Classroom & hostel capacity benchmarks and breakdowns
    """
    stats = get_dashboard_stats()

    # 1. Students by department
    q_students_dept = """
        SELECT 
            NVL(d.DEPT_NAME, 'Unassigned') AS label,
            COUNT(s.SID) AS val
        FROM DEPARTMENT1143 d
        LEFT JOIN STUDENT1143 s ON d.DEPT_ID = s.DEPT_ID
        GROUP BY d.DEPT_ID, d.DEPT_NAME
        ORDER BY val DESC, d.DEPT_NAME ASC
    """
    students_by_dept = execute_read_query(q_students_dept)

    # 2. Faculty by department
    q_faculty_dept = """
        SELECT 
            NVL(d.DEPT_NAME, 'Unassigned') AS label,
            COUNT(f.FID) AS val
        FROM DEPARTMENT1143 d
        LEFT JOIN FACULTY1143 f ON d.DEPT_ID = f.DEPT_ID
        GROUP BY d.DEPT_ID, d.DEPT_NAME
        ORDER BY val DESC, d.DEPT_NAME ASC
    """
    faculty_by_dept = execute_read_query(q_faculty_dept)

    # 3. Courses by department
    q_courses_dept = """
        SELECT 
            NVL(d.DEPT_NAME, 'Unassigned') AS label,
            COUNT(c.COURSE_ID) AS val
        FROM DEPARTMENT1143 d
        LEFT JOIN COURSE1143 c ON d.DEPT_ID = c.DEPT_ID
        GROUP BY d.DEPT_ID, d.DEPT_NAME
        ORDER BY val DESC, d.DEPT_NAME ASC
    """
    courses_by_dept = execute_read_query(q_courses_dept)

    # 4. Result grade distribution (Canonical order S, A, B, C, D, E, F)
    q_grade_dist = """
        SELECT 
            TRIM(GRADE) AS label,
            COUNT(*) AS val
        FROM RESULT1143
        WHERE GRADE IS NOT NULL
        GROUP BY TRIM(GRADE)
        ORDER BY 
            CASE TRIM(GRADE)
                WHEN 'S' THEN 1
                WHEN 'A' THEN 2
                WHEN 'B' THEN 3
                WHEN 'C' THEN 4
                WHEN 'D' THEN 5
                WHEN 'E' THEN 6
                WHEN 'F' THEN 7
                ELSE 8
            END
    """
    grade_distribution = execute_read_query(q_grade_dist)

    # 5. Top examinations by course
    q_exams_course = """
        SELECT 
            c.COURSE_NAME AS label,
            COUNT(e.EXAM_ID) AS val
        FROM COURSE1143 c
        JOIN EXAM1143 e ON c.COURSE_ID = e.COURSE_ID
        GROUP BY c.COURSE_ID, c.COURSE_NAME
        ORDER BY val DESC, c.COURSE_NAME ASC
        FETCH FIRST 8 ROWS ONLY
    """
    exams_by_course = execute_read_query(q_exams_course)

    # 6. University-wise department counts
    q_dept_uni = """
        SELECT 
            u.UNAME AS label,
            COUNT(d.DEPT_ID) AS val
        FROM UNIVERSITY1143 u
        LEFT JOIN DEPARTMENT1143 d ON u.UNID = d.UNID
        GROUP BY u.UNID, u.UNAME
        ORDER BY val DESC, u.UNAME ASC
    """
    dept_by_university = execute_read_query(q_dept_uni)

    # 7. Classroom and Hostel capacity summaries
    q_class_summary = """
        SELECT 
            COUNT(ROOM_NO) AS total_rooms,
            NVL(SUM(CAPACITY), 0) AS total_capacity,
            NVL(ROUND(AVG(CAPACITY), 1), 0) AS avg_capacity,
            NVL(MAX(CAPACITY), 0) AS max_capacity,
            NVL(MIN(CAPACITY), 0) AS min_capacity
        FROM CLASSROOM1143
    """
    classroom_summary = execute_read_scalar_row(q_class_summary, default={
        "TOTAL_ROOMS": 0, "TOTAL_CAPACITY": 0, "AVG_CAPACITY": 0, "MAX_CAPACITY": 0, "MIN_CAPACITY": 0
    })

    q_hostel_summary = """
        SELECT 
            COUNT(HOSTEL_ID) AS total_hostels,
            NVL(SUM(CAPACITY), 0) AS total_capacity,
            NVL(ROUND(AVG(CAPACITY), 1), 0) AS avg_capacity,
            NVL(MAX(CAPACITY), 0) AS max_capacity,
            NVL(MIN(CAPACITY), 0) AS min_capacity
        FROM HOSTEL1143
    """
    hostel_summary = execute_read_scalar_row(q_hostel_summary, default={
        "TOTAL_HOSTELS": 0, "TOTAL_CAPACITY": 0, "AVG_CAPACITY": 0, "MAX_CAPACITY": 0, "MIN_CAPACITY": 0
    })

    # 8. Hostel capacity by university
    q_hostel_uni = """
        SELECT 
            u.UNAME AS label,
            NVL(SUM(h.CAPACITY), 0) AS val,
            COUNT(h.HOSTEL_ID) AS count
        FROM UNIVERSITY1143 u
        LEFT JOIN HOSTEL1143 h ON u.UNID = h.UNID
        GROUP BY u.UNID, u.UNAME
        ORDER BY val DESC, u.UNAME ASC
    """
    hostel_by_university = execute_read_query(q_hostel_uni)

    # 9. Classroom capacity by department (Top 8)
    q_class_dept = """
        SELECT 
            d.DEPT_NAME AS label,
            NVL(SUM(cl.CAPACITY), 0) AS val,
            COUNT(cl.ROOM_NO) AS count
        FROM DEPARTMENT1143 d
        JOIN CLASSROOM1143 cl ON d.DEPT_ID = cl.DEPT_ID
        GROUP BY d.DEPT_ID, d.DEPT_NAME
        ORDER BY val DESC, d.DEPT_NAME ASC
        FETCH FIRST 8 ROWS ONLY
    """
    classroom_by_dept = execute_read_query(q_class_dept)

    return {
        "stats": stats,
        "students_by_dept": students_by_dept,
        "faculty_by_dept": faculty_by_dept,
        "courses_by_dept": courses_by_dept,
        "grade_distribution": grade_distribution,
        "exams_by_course": exams_by_course,
        "dept_by_university": dept_by_university,
        "classroom_summary": classroom_summary,
        "hostel_summary": hostel_summary,
        "hostel_by_university": hostel_by_university,
        "classroom_by_dept": classroom_by_dept
    }

# ==============================================================================
# Record Insertion & Write Helpers (Safe, Parameterized, Transactional)
# ==============================================================================

def handle_db_write_error(e):
    """
    Format Oracle Database write errors into user-friendly messages without leaking credentials.
    """
    err_str = str(e)
    if "ORA-00001" in err_str:
        return "Duplicate Key Violation: A record with this Primary Key or unique identifier already exists."
    elif "ORA-02292" in err_str:
        return "Integrity Constraint Violation: Cannot delete or update this record because related dependent records exist in other tables. Dependent records must be addressed or removed first."
    elif "ORA-02291" in err_str:
        return "Integrity Constraint Violation: The selected related record (Foreign Key) does not exist in the database."
    elif "ORA-02290" in err_str:
        return "Check Constraint Violation: The submitted data violates table constraints (e.g., positive salary/capacity, valid mark/grade/gender)."
    elif "ORA-01400" in err_str:
        return "Mandatory Field Missing: A required column was omitted or empty."
    elif "ORA-12899" in err_str:
        return "Value Too Large: One of the text inputs exceeds the maximum allowed length."
    return "Database Operation Failed: The requested database operation could not be completed. Please verify all fields and constraints, then try again."

def execute_write_query(query, params=None):
    """
    Execute a parameterized INSERT/UPDATE/DELETE statement inside a strict transaction.
    Commits on success; explicitly rolls back on exception.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or {})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

ALLOWED_ID_TABLES = {
    "UNIVERSITY1143": "UNID",
    "DEPARTMENT1143": "DEPT_ID",
    "FACULTY1143": "FID",
    "STUDENT1143": "SID",
    "COURSE1143": "COURSE_ID",
    "CLASSROOM1143": "ROOM_NO",
    "EXAM1143": "EXAM_ID",
    "RESULT1143": "RESULT_ID",
    "LIBRARY1143": "BOOK_ID",
    "HOSTEL1143": "HOSTEL_ID"
}

def get_next_id(table_name, id_column):
    """
    Safely retrieve the next suggested ID (MAX + 1) for a table from an allowlist.
    """
    if table_name not in ALLOWED_ID_TABLES or ALLOWED_ID_TABLES[table_name] != id_column:
        raise ValueError(f"Invalid table ({table_name}) or column ({id_column}) for ID lookup.")
    query = f"SELECT NVL(MAX({id_column}), 0) + 1 AS NEXT_ID FROM {table_name}"
    res = execute_read_scalar_row(query, default={"NEXT_ID": 1})
    return int(res.get("NEXT_ID", 1))

def check_id_exists(table_name, id_column, id_val):
    """
    Check if an ID already exists in a given table.
    """
    if table_name not in ALLOWED_ID_TABLES or ALLOWED_ID_TABLES[table_name] != id_column:
        raise ValueError(f"Invalid table or column identifier.")
    query = f"SELECT 1 FROM {table_name} WHERE {id_column} = :id_val"
    rows = execute_read_query(query, {"id_val": id_val})
    return len(rows) > 0

# Dropdowns for Add Record Forms
def get_universities_dropdown():
    return execute_read_query("SELECT UNID, UNAME, LOCATION FROM UNIVERSITY1143 ORDER BY UNAME")

def get_departments_dropdown():
    return execute_read_query("""
        SELECT d.DEPT_ID, d.DEPT_NAME, u.UNAME 
        FROM DEPARTMENT1143 d 
        LEFT JOIN UNIVERSITY1143 u ON d.UNID = u.UNID 
        ORDER BY d.DEPT_NAME
    """)

def get_faculty_dropdown():
    return execute_read_query("""
        SELECT f.FID, f.FNAME, f.DESIGNATION, d.DEPT_NAME 
        FROM FACULTY1143 f 
        LEFT JOIN DEPARTMENT1143 d ON f.DEPT_ID = d.DEPT_ID 
        ORDER BY f.FNAME
    """)

def get_students_dropdown():
    return execute_read_query("""
        SELECT s.SID, s.SNAME, d.DEPT_NAME 
        FROM STUDENT1143 s 
        LEFT JOIN DEPARTMENT1143 d ON s.DEPT_ID = d.DEPT_ID 
        ORDER BY s.SNAME
    """)

def get_courses_dropdown():
    return execute_read_query("""
        SELECT c.COURSE_ID, c.COURSE_NAME, d.DEPT_NAME 
        FROM COURSE1143 c 
        LEFT JOIN DEPARTMENT1143 d ON c.DEPT_ID = d.DEPT_ID 
        ORDER BY c.COURSE_NAME
    """)

def get_classrooms_dropdown():
    return execute_read_query("""
        SELECT cl.ROOM_NO, cl.CAPACITY, d.DEPT_NAME 
        FROM CLASSROOM1143 cl 
        LEFT JOIN DEPARTMENT1143 d ON cl.DEPT_ID = d.DEPT_ID 
        ORDER BY cl.ROOM_NO
    """)

def get_exams_dropdown():
    return execute_read_query("""
        SELECT e.EXAM_ID, e.EXAM_NAME, c.COURSE_NAME, TO_CHAR(e.EXAM_DATE, 'YYYY-MM-DD') AS EXAM_DATE 
        FROM EXAM1143 e 
        LEFT JOIN COURSE1143 c ON e.COURSE_ID = c.COURSE_ID 
        ORDER BY e.EXAM_ID
    """)

# Parameterized Table Insertions
def insert_university(unid, uname, location):
    query = "INSERT INTO UNIVERSITY1143 (UNID, UNAME, LOCATION) VALUES (:unid, :uname, :location)"
    execute_write_query(query, {"unid": int(unid), "uname": uname.strip(), "location": location.strip()})

def insert_department(dept_id, dept_name, unid):
    query = "INSERT INTO DEPARTMENT1143 (DEPT_ID, DEPT_NAME, UNID) VALUES (:dept_id, :dept_name, :unid)"
    unid_val = int(unid) if unid and str(unid).strip() else None
    execute_write_query(query, {"dept_id": int(dept_id), "dept_name": dept_name.strip(), "unid": unid_val})

def insert_faculty(fid, fname, designation, salary, dept_id):
    query = "INSERT INTO FACULTY1143 (FID, FNAME, DESIGNATION, SALARY, DEPT_ID) VALUES (:fid, :fname, :designation, :salary, :dept_id)"
    dept_val = int(dept_id) if dept_id and str(dept_id).strip() else None
    desig_val = designation.strip() if designation and designation.strip() else None
    execute_write_query(query, {
        "fid": int(fid),
        "fname": fname.strip(),
        "designation": desig_val,
        "salary": float(salary),
        "dept_id": dept_val
    })

def insert_student(sid, sname, dob, gender, address, dept_id):
    query = """
        INSERT INTO STUDENT1143 (SID, SNAME, DOB, GENDER, ADDRESS, DEPT_ID) 
        VALUES (:sid, :sname, TO_DATE(:dob, 'YYYY-MM-DD'), :gender, :address, :dept_id)
    """
    dept_val = int(dept_id) if dept_id and str(dept_id).strip() else None
    addr_val = address.strip() if address and address.strip() else None
    execute_write_query(query, {
        "sid": int(sid),
        "sname": sname.strip(),
        "dob": dob.strip(),
        "gender": gender.strip().upper(),
        "address": addr_val,
        "dept_id": dept_val
    })

def insert_course(course_id, course_name, credits, dept_id, fid):
    query = "INSERT INTO COURSE1143 (COURSE_ID, COURSE_NAME, CREDITS, DEPT_ID, FID) VALUES (:course_id, :course_name, :credits, :dept_id, :fid)"
    credits_val = int(credits) if credits and str(credits).strip() else None
    dept_val = int(dept_id) if dept_id and str(dept_id).strip() else None
    fid_val = int(fid) if fid and str(fid).strip() else None
    execute_write_query(query, {
        "course_id": int(course_id),
        "course_name": course_name.strip(),
        "credits": credits_val,
        "dept_id": dept_val,
        "fid": fid_val
    })

def insert_classroom(room_no, capacity, dept_id):
    query = "INSERT INTO CLASSROOM1143 (ROOM_NO, CAPACITY, DEPT_ID) VALUES (:room_no, :capacity, :dept_id)"
    cap_val = int(capacity) if capacity and str(capacity).strip() else None
    dept_val = int(dept_id) if dept_id and str(dept_id).strip() else None
    execute_write_query(query, {
        "room_no": int(room_no),
        "capacity": cap_val,
        "dept_id": dept_val
    })

def insert_exam(exam_id, exam_name, exam_date, course_id, room_no):
    query = """
        INSERT INTO EXAM1143 (EXAM_ID, EXAM_NAME, EXAM_DATE, COURSE_ID, ROOM_NO) 
        VALUES (:exam_id, :exam_name, TO_DATE(:exam_date, 'YYYY-MM-DD'), :course_id, :room_no)
    """
    cid_val = int(course_id) if course_id and str(course_id).strip() else None
    room_val = int(room_no) if room_no and str(room_no).strip() else None
    execute_write_query(query, {
        "exam_id": int(exam_id),
        "exam_name": exam_name.strip(),
        "exam_date": exam_date.strip(),
        "course_id": cid_val,
        "room_no": room_val
    })

def insert_result(result_id, grade, marks, sid, exam_id):
    query = "INSERT INTO RESULT1143 (RESULT_ID, GRADE, MARKS, SID, EXAM_ID) VALUES (:result_id, :grade, :marks, :sid, :exam_id)"
    grade_val = grade.strip().upper() if grade and grade.strip() else None
    marks_val = float(marks) if marks is not None and str(marks).strip() != "" else None
    sid_val = int(sid) if sid and str(sid).strip() else None
    exam_val = int(exam_id) if exam_id and str(exam_id).strip() else None
    execute_write_query(query, {
        "result_id": int(result_id),
        "grade": grade_val,
        "marks": marks_val,
        "sid": sid_val,
        "exam_id": exam_val
    })

def insert_library(book_id, title, author, unid):
    query = "INSERT INTO LIBRARY1143 (BOOK_ID, TITLE, AUTHOR, UNID) VALUES (:book_id, :title, :author, :unid)"
    unid_val = int(unid) if unid and str(unid).strip() else None
    execute_write_query(query, {
        "book_id": int(book_id),
        "title": title.strip(),
        "author": author.strip(),
        "unid": unid_val
    })

def insert_hostel(hostel_id, hostel_name, capacity, unid):
    query = "INSERT INTO HOSTEL1143 (HOSTEL_ID, HOSTEL_NAME, CAPACITY, UNID) VALUES (:hostel_id, :hostel_name, :capacity, :unid)"
    cap_val = int(capacity) if capacity and str(capacity).strip() else None
    unid_val = int(unid) if unid and str(unid).strip() else None
    execute_write_query(query, {
        "hostel_id": int(hostel_id),
        "hostel_name": hostel_name.strip(),
        "capacity": cap_val,
        "unid": unid_val
    })

# ==============================================================================
# Record Retrieval By ID (For Pre-filling Edit Forms)
# ==============================================================================

def get_university_by_id(unid):
    rows = execute_read_query("SELECT UNID, UNAME, LOCATION FROM UNIVERSITY1143 WHERE UNID = :unid", {"unid": int(unid)})
    return rows[0] if rows else None

def get_department_by_id(dept_id):
    rows = execute_read_query("SELECT DEPT_ID, DEPT_NAME, UNID FROM DEPARTMENT1143 WHERE DEPT_ID = :dept_id", {"dept_id": int(dept_id)})
    return rows[0] if rows else None

def get_faculty_by_id(fid):
    rows = execute_read_query("SELECT FID, FNAME, DESIGNATION, SALARY, DEPT_ID FROM FACULTY1143 WHERE FID = :fid", {"fid": int(fid)})
    return rows[0] if rows else None

def get_student_by_id(sid):
    rows = execute_read_query("""
        SELECT SID, SNAME, TO_CHAR(DOB, 'YYYY-MM-DD') AS DOB, GENDER, ADDRESS, DEPT_ID 
        FROM STUDENT1143 
        WHERE SID = :sid
    """, {"sid": int(sid)})
    return rows[0] if rows else None

def get_course_by_id(course_id):
    rows = execute_read_query("SELECT COURSE_ID, COURSE_NAME, CREDITS, DEPT_ID, FID FROM COURSE1143 WHERE COURSE_ID = :course_id", {"course_id": int(course_id)})
    return rows[0] if rows else None

def get_classroom_by_id(room_no):
    rows = execute_read_query("SELECT ROOM_NO, CAPACITY, DEPT_ID FROM CLASSROOM1143 WHERE ROOM_NO = :room_no", {"room_no": int(room_no)})
    return rows[0] if rows else None

def get_exam_by_id(exam_id):
    rows = execute_read_query("""
        SELECT EXAM_ID, EXAM_NAME, TO_CHAR(EXAM_DATE, 'YYYY-MM-DD') AS EXAM_DATE, COURSE_ID, ROOM_NO 
        FROM EXAM1143 
        WHERE EXAM_ID = :exam_id
    """, {"exam_id": int(exam_id)})
    return rows[0] if rows else None

def get_result_by_id(result_id):
    rows = execute_read_query("SELECT RESULT_ID, GRADE, MARKS, SID, EXAM_ID FROM RESULT1143 WHERE RESULT_ID = :result_id", {"result_id": int(result_id)})
    return rows[0] if rows else None

def get_library_by_id(book_id):
    rows = execute_read_query("SELECT BOOK_ID, TITLE, AUTHOR, UNID FROM LIBRARY1143 WHERE BOOK_ID = :book_id", {"book_id": int(book_id)})
    return rows[0] if rows else None

def get_hostel_by_id(hostel_id):
    rows = execute_read_query("SELECT HOSTEL_ID, HOSTEL_NAME, CAPACITY, UNID FROM HOSTEL1143 WHERE HOSTEL_ID = :hostel_id", {"hostel_id": int(hostel_id)})
    return rows[0] if rows else None

# ==============================================================================
# Record Update Functions (Safe, Parameterized, Transactional)
# ==============================================================================

def update_university(unid, uname, location):
    query = "UPDATE UNIVERSITY1143 SET UNAME = :uname, LOCATION = :location WHERE UNID = :unid"
    execute_write_query(query, {"unid": int(unid), "uname": uname.strip(), "location": location.strip()})

def update_department(dept_id, dept_name, unid):
    query = "UPDATE DEPARTMENT1143 SET DEPT_NAME = :dept_name, UNID = :unid WHERE DEPT_ID = :dept_id"
    unid_val = int(unid) if unid and str(unid).strip() else None
    execute_write_query(query, {"dept_id": int(dept_id), "dept_name": dept_name.strip(), "unid": unid_val})

def update_faculty(fid, fname, designation, salary, dept_id):
    query = "UPDATE FACULTY1143 SET FNAME = :fname, DESIGNATION = :designation, SALARY = :salary, DEPT_ID = :dept_id WHERE FID = :fid"
    dept_val = int(dept_id) if dept_id and str(dept_id).strip() else None
    desig_val = designation.strip() if designation and designation.strip() else None
    execute_write_query(query, {
        "fid": int(fid),
        "fname": fname.strip(),
        "designation": desig_val,
        "salary": float(salary),
        "dept_id": dept_val
    })

def update_student(sid, sname, dob, gender, address, dept_id):
    query = """
        UPDATE STUDENT1143 
        SET SNAME = :sname, DOB = TO_DATE(:dob, 'YYYY-MM-DD'), GENDER = :gender, ADDRESS = :address, DEPT_ID = :dept_id 
        WHERE SID = :sid
    """
    dept_val = int(dept_id) if dept_id and str(dept_id).strip() else None
    addr_val = address.strip() if address and address.strip() else None
    execute_write_query(query, {
        "sid": int(sid),
        "sname": sname.strip(),
        "dob": dob.strip(),
        "gender": gender.strip().upper(),
        "address": addr_val,
        "dept_id": dept_val
    })

def update_course(course_id, course_name, credits, dept_id, fid):
    query = "UPDATE COURSE1143 SET COURSE_NAME = :course_name, CREDITS = :credits, DEPT_ID = :dept_id, FID = :fid WHERE COURSE_ID = :course_id"
    credits_val = int(credits) if credits and str(credits).strip() else None
    dept_val = int(dept_id) if dept_id and str(dept_id).strip() else None
    fid_val = int(fid) if fid and str(fid).strip() else None
    execute_write_query(query, {
        "course_id": int(course_id),
        "course_name": course_name.strip(),
        "credits": credits_val,
        "dept_id": dept_val,
        "fid": fid_val
    })

def update_classroom(room_no, capacity, dept_id):
    query = "UPDATE CLASSROOM1143 SET CAPACITY = :capacity, DEPT_ID = :dept_id WHERE ROOM_NO = :room_no"
    cap_val = int(capacity) if capacity and str(capacity).strip() else None
    dept_val = int(dept_id) if dept_id and str(dept_id).strip() else None
    execute_write_query(query, {
        "room_no": int(room_no),
        "capacity": cap_val,
        "dept_id": dept_val
    })

def update_exam(exam_id, exam_name, exam_date, course_id, room_no):
    query = """
        UPDATE EXAM1143 
        SET EXAM_NAME = :exam_name, EXAM_DATE = TO_DATE(:exam_date, 'YYYY-MM-DD'), COURSE_ID = :course_id, ROOM_NO = :room_no 
        WHERE EXAM_ID = :exam_id
    """
    cid_val = int(course_id) if course_id and str(course_id).strip() else None
    room_val = int(room_no) if room_no and str(room_no).strip() else None
    execute_write_query(query, {
        "exam_id": int(exam_id),
        "exam_name": exam_name.strip(),
        "exam_date": exam_date.strip(),
        "course_id": cid_val,
        "room_no": room_val
    })

def update_result(result_id, grade, marks, sid, exam_id):
    query = "UPDATE RESULT1143 SET GRADE = :grade, MARKS = :marks, SID = :sid, EXAM_ID = :exam_id WHERE RESULT_ID = :result_id"
    grade_val = grade.strip().upper() if grade and grade.strip() else None
    marks_val = float(marks) if marks is not None and str(marks).strip() != "" else None
    sid_val = int(sid) if sid and str(sid).strip() else None
    exam_val = int(exam_id) if exam_id and str(exam_id).strip() else None
    execute_write_query(query, {
        "result_id": int(result_id),
        "grade": grade_val,
        "marks": marks_val,
        "sid": sid_val,
        "exam_id": exam_val
    })

def update_library(book_id, title, author, unid):
    query = "UPDATE LIBRARY1143 SET TITLE = :title, AUTHOR = :author, UNID = :unid WHERE BOOK_ID = :book_id"
    unid_val = int(unid) if unid and str(unid).strip() else None
    execute_write_query(query, {
        "book_id": int(book_id),
        "title": title.strip(),
        "author": author.strip(),
        "unid": unid_val
    })

def update_hostel(hostel_id, hostel_name, capacity, unid):
    query = "UPDATE HOSTEL1143 SET HOSTEL_NAME = :hostel_name, CAPACITY = :capacity, UNID = :unid WHERE HOSTEL_ID = :hostel_id"
    cap_val = int(capacity) if capacity and str(capacity).strip() else None
    unid_val = int(unid) if unid and str(unid).strip() else None
    execute_write_query(query, {
        "hostel_id": int(hostel_id),
        "hostel_name": hostel_name.strip(),
        "capacity": cap_val,
        "unid": unid_val
    })

# ==============================================================================
# Record Deletion Functions (Safe, Parameterized, Transactional)
# ==============================================================================

def delete_record(table_name, id_column, id_val):
    """
    Safely delete a single record by primary key inside an allowlisted table.
    """
    if table_name not in ALLOWED_ID_TABLES or ALLOWED_ID_TABLES[table_name] != id_column:
        raise ValueError(f"Invalid table ({table_name}) or column ({id_column}) for deletion.")
    query = f"DELETE FROM {table_name} WHERE {id_column} = :id_val"
    execute_write_query(query, {"id_val": int(id_val)})

def delete_university(unid):
    delete_record("UNIVERSITY1143", "UNID", unid)

def delete_department(dept_id):
    delete_record("DEPARTMENT1143", "DEPT_ID", dept_id)

def delete_faculty(fid):
    delete_record("FACULTY1143", "FID", fid)

def delete_student(sid):
    delete_record("STUDENT1143", "SID", sid)

def delete_course(course_id):
    delete_record("COURSE1143", "COURSE_ID", course_id)

def delete_classroom(room_no):
    delete_record("CLASSROOM1143", "ROOM_NO", room_no)

def delete_exam(exam_id):
    delete_record("EXAM1143", "EXAM_ID", exam_id)

def delete_result(result_id):
    delete_record("RESULT1143", "RESULT_ID", result_id)

def delete_library(book_id):
    delete_record("LIBRARY1143", "BOOK_ID", book_id)

def delete_hostel(hostel_id):
    delete_record("HOSTEL1143", "HOSTEL_ID", hostel_id)

